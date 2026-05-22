"""实时/回放一体化 6DoF 推理流水线。"""

from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import dataclass

import numpy as np

from .camera.d455 import D455Stream
from .config import ProjectConfig, load_config
from .mocap.csv_provider import CSVRigidBodyProvider
from .object_model import build_object_edges, build_object_keypoints
from .pose.temporal_filter import TemporalPoseFilter
from .pose.yolo6d_interface import JSONReplayBackend, UltralyticsLiveBackend, YOLO6DPoseEstimator
from .transforms import compose_poses, invert_pose, matrix_to_euler_xyz_deg, matrix_to_quaternion
from .types import CameraIntrinsics, ImageFrame, PoseEstimate, PoseSE3
from .visualization import draw_pose_overlay


@dataclass(slots=True)
class PipelineResult:
    """单帧 pipeline 输出，集中传给日志、窗口和 CSV 写入逻辑。"""

    frame_index: int
    timestamp_s: float
    raw_prediction: PoseEstimate | None
    prediction: PoseEstimate | None
    mocap_pose: PoseSE3 | None
    backend_debug: dict[str, object]


class ReplayFrameSource:
    """给 JSON replay 模式使用的假图像源。"""

    def __init__(self, intrinsics: CameraIntrinsics, frame_timestamps_s: list[float], image_size: tuple[int, int]) -> None:
        self._intrinsics = intrinsics
        self._timestamps = frame_timestamps_s
        self._image_size = image_size
        self._index = 0

    def start(self) -> None:
        """保持和真实 D455Stream 一样的接口。"""
        return None

    def stop(self) -> None:
        """保持和真实 D455Stream 一样的接口。"""
        return None

    def wait_for_frame(self) -> ImageFrame:
        """按 replay 时间戳生成黑图帧，只用于驱动后端和 Mocap 对齐逻辑。"""
        if self._index >= len(self._timestamps):
            raise StopIteration

        height, width = self._image_size
        frame = ImageFrame(
            color=np.zeros((height, width, 3), dtype=np.uint8),
            depth=None,
            timestamp_s=self._timestamps[self._index],
            intrinsics=self._intrinsics,
        )
        self._index += 1
        return frame


class PosePipeline:
    """把取流、检测、PnP、滤波、Mocap 对比和可视化串起来的主流水线。"""

    def __init__(self, config: ProjectConfig) -> None:
        self.config = config
        # object_model_config 复用 object_model.py 的字典接口，避免重复写模型构造逻辑。
        object_model_config = {
            "keypoints_mode": config.object_model.keypoints_mode,
            "dimensions_m": config.object_model.dimensions_m,
            "extents_m": config.object_model.extents_m,
            "model_json_path": None if config.object_model.model_json_path is None else str(config.object_model.model_json_path),
            "include_center": config.object_model.include_center,
        }
        self.object_points_xyz = build_object_keypoints(object_model_config)
        self.object_edges = build_object_edges(object_model_config)

        self.yolo_backend = self._build_yolo_backend()
        self.pose_estimator = YOLO6DPoseEstimator(
            backend=self.yolo_backend,
            object_points_xyz=self.object_points_xyz,
            conf_threshold=self.config.yolo6d.conf_threshold,
            pnp_config=self.config.yolo6d.pnp,
        )
        self.pose_filter = TemporalPoseFilter(self.config.yolo6d.temporal_filter)
        self.mocap_provider = self._build_mocap_provider()
        self.frame_source = self._build_frame_source()
        self._csv_writer = None
        self._csv_file = None
        self._last_perf_counter_s: float | None = None
        self._smoothed_fps: float | None = None

    def _build_yolo_backend(self):
        """根据配置创建 replay 后端或实时 Ultralytics 后端。"""
        backend = self.config.yolo6d.backend.lower()
        if backend == "json_replay":
            if self.config.yolo6d.replay_json_path is None:
                raise ValueError("backend 'json_replay' requires yolo6d.replay_json_path")
            return JSONReplayBackend(
                json_path=self.config.yolo6d.replay_json_path,
                timestamp_tolerance_s=self.config.yolo6d.replay_timestamp_tolerance_s,
            )
        if backend == "ultralytics_live":
            if self.config.yolo6d.model_path is None:
                raise ValueError("backend 'ultralytics_live' requires yolo6d.model_path")
            return UltralyticsLiveBackend(
                model_path=self.config.yolo6d.model_path,
                label=self.config.object_model.label,
                roi_tracker=self.config.yolo6d.roi_tracker,
                conf_threshold=self.config.yolo6d.conf_threshold,
                imgsz=self.config.yolo6d.inference_imgsz,
                device=self.config.yolo6d.inference_device,
            )
        raise ValueError(
            f"Unsupported YOLO backend: {self.config.yolo6d.backend}. Supported backends are 'json_replay' and 'ultralytics_live'."
        )

    def _build_mocap_provider(self) -> CSVRigidBodyProvider | None:
        """按需创建 Mocap CSV 查询器；实时纯推理时可以不启用。"""
        if not self.config.mocap.enabled:
            return None

        mode = self.config.mocap.mode.lower()
        if mode != "csv":
            raise ValueError("Only mocap mode 'csv' is implemented in this baseline.")
        if self.config.mocap.csv_path is None:
            raise ValueError("mocap.enabled=true requires mocap.csv_path")
        return CSVRigidBodyProvider(self.config.mocap.csv_path)

    def _build_frame_source(self) -> D455Stream | ReplayFrameSource:
        """根据后端模式选择真实 D455 或 replay 帧源。"""
        if self.config.yolo6d.backend.lower() == "json_replay":
            replay_backend = self.yolo_backend
            # replay 用预测文件中的时间戳驱动 pipeline，而不需要真实图像。
            frame_timestamps_s = [timestamp for timestamp, _ in replay_backend._frames_by_timestamp]
            if not frame_timestamps_s:
                frame_timestamps_s = [0.0]
            intrinsics = CameraIntrinsics(
                fx=910.0,
                fy=910.0,
                cx=self.config.camera.color_width / 2.0,
                cy=self.config.camera.color_height / 2.0,
                width=self.config.camera.color_width,
                height=self.config.camera.color_height,
                dist_coeffs=np.zeros(5, dtype=np.float64),
            )
            return ReplayFrameSource(
                intrinsics=intrinsics,
                frame_timestamps_s=frame_timestamps_s,
                image_size=(self.config.camera.color_height, self.config.camera.color_width),
            )

        if self.config.camera.source.lower() != "d455":
            raise ValueError("Only camera source 'd455' is implemented.")
        return D455Stream(self.config.camera)

    def _ensure_csv_writer(self) -> None:
        """懒创建 CSV writer，只有配置 save_csv 时才落盘。"""
        save_csv = self.config.output.save_csv
        if save_csv is None or self._csv_writer is not None:
            return None

        save_csv.parent.mkdir(parents=True, exist_ok=True)
        self._csv_file = save_csv.open("w", encoding="utf-8", newline="")
        self._csv_writer = csv.DictWriter(
            self._csv_file,
            fieldnames=[
                "frame_index",
                "timestamp_s",
                "prediction_tx",
                "prediction_ty",
                "prediction_tz",
                "prediction_qx",
                "prediction_qy",
                "prediction_qz",
                "prediction_qw",
                "prediction_reproj_px",
                "prediction_confidence",
                "prediction_source",
                "mocap_tx",
                "mocap_ty",
                "mocap_tz",
                "mocap_qx",
                "mocap_qy",
                "mocap_qz",
                "mocap_qw",
            ],
        )
        self._csv_writer.writeheader()
        return None

    def _write_result(self, result: PipelineResult) -> None:
        """把预测位姿和可选 Mocap GT 写成一行 CSV。"""
        if self._csv_writer is None:
            return None

        row = {
            "frame_index": result.frame_index,
            "timestamp_s": f"{result.timestamp_s:.6f}",
            "prediction_tx": "",
            "prediction_ty": "",
            "prediction_tz": "",
            "prediction_qx": "",
            "prediction_qy": "",
            "prediction_qz": "",
            "prediction_qw": "",
            "prediction_reproj_px": "",
            "prediction_confidence": "",
            "prediction_source": "",
            "mocap_tx": "",
            "mocap_ty": "",
            "mocap_tz": "",
            "mocap_qx": "",
            "mocap_qy": "",
            "mocap_qz": "",
            "mocap_qw": "",
        }

        if result.prediction is not None:
            pose = result.prediction.pose
            qx, qy, qz, qw = matrix_to_quaternion(pose.rotation)
            row.update(
                {
                    "prediction_tx": f"{pose.translation_m[0]:.6f}",
                    "prediction_ty": f"{pose.translation_m[1]:.6f}",
                    "prediction_tz": f"{pose.translation_m[2]:.6f}",
                    "prediction_qx": f"{qx:.6f}",
                    "prediction_qy": f"{qy:.6f}",
                    "prediction_qz": f"{qz:.6f}",
                    "prediction_qw": f"{qw:.6f}",
                    "prediction_reproj_px": f"{result.prediction.reprojection_error_px:.4f}",
                    "prediction_confidence": f"{result.prediction.confidence:.4f}",
                    "prediction_source": result.prediction.source,
                }
            )

        if result.mocap_pose is not None:
            qx, qy, qz, qw = matrix_to_quaternion(result.mocap_pose.rotation)
            row.update(
                {
                    "mocap_tx": f"{result.mocap_pose.translation_m[0]:.6f}",
                    "mocap_ty": f"{result.mocap_pose.translation_m[1]:.6f}",
                    "mocap_tz": f"{result.mocap_pose.translation_m[2]:.6f}",
                    "mocap_qx": f"{qx:.6f}",
                    "mocap_qy": f"{qy:.6f}",
                    "mocap_qz": f"{qz:.6f}",
                    "mocap_qw": f"{qw:.6f}",
                }
            )

        self._csv_writer.writerow(row)
        return None

    def _world_camera_optical_pose(self, timestamp_s: float) -> PoseSE3 | None:
        """计算 T_world_camera_optical，支持静态固定相机和动捕相机刚体两种模式。"""
        mocap_timestamp_s = timestamp_s + self.config.mocap.time_offset_s
        static_world_camera_optical = self.config.mocap.world_camera_optical
        if static_world_camera_optical is not None:
            # 固定相机模式：相机世界位姿来自 YAML，不需要逐帧查相机刚体。
            return PoseSE3(
                parent_frame=static_world_camera_optical.parent_frame,
                child_frame=static_world_camera_optical.child_frame,
                rotation=static_world_camera_optical.rotation.copy(),
                translation_m=static_world_camera_optical.translation_m.copy(),
                timestamp_s=timestamp_s,
            )

        if self.mocap_provider is None:
            return None
        if self.config.mocap.camera_rigid_body is None:
            return None
        if self.config.mocap.camera_rigid_to_optical is None:
            return None

        # 动捕模式：T_world_camera_optical = T_world_camera_rigid * T_camera_rigid_to_optical。
        camera_rigid_pose = self.mocap_provider.get_pose(
            rigid_body=self.config.mocap.camera_rigid_body,
            timestamp_s=mocap_timestamp_s,
            max_time_diff_s=self.config.mocap.max_time_diff_s,
        )
        if camera_rigid_pose is None:
            return None
        return compose_poses(camera_rigid_pose, self.config.mocap.camera_rigid_to_optical)

    def _compute_mocap_pose(self, timestamp_s: float) -> PoseSE3 | None:
        """把 Mocap 中的物体刚体位姿转换到相机光学坐标系下，作为 GT 对比。"""
        if self.mocap_provider is None:
            return None

        world_camera_optical = self._world_camera_optical_pose(timestamp_s)
        if world_camera_optical is None:
            return None

        mocap_timestamp_s = timestamp_s + self.config.mocap.time_offset_s
        object_rigid_pose = self.mocap_provider.get_pose(
            rigid_body=self.config.mocap.object_rigid_body,
            timestamp_s=mocap_timestamp_s,
            max_time_diff_s=self.config.mocap.max_time_diff_s,
        )
        if object_rigid_pose is None:
            return None

        # 坐标链：camera_optical <- world <- object_rigid <- object_model。
        world_object_model = compose_poses(object_rigid_pose, self.config.mocap.object_rigid_to_model)
        camera_optical_world = invert_pose(world_camera_optical)
        return compose_poses(camera_optical_world, world_object_model)

    def run(self, max_frames: int | None = None) -> None:
        """主循环：取一帧、估计位姿、更新滤波、输出日志/窗口。"""
        self._ensure_csv_writer()
        self.frame_source.start()
        frame_index = 0

        try:
            while max_frames is None or frame_index < max_frames:
                frame = self.frame_source.wait_for_frame()
                # raw_prediction 是单帧 PnP 输出；prediction 是时间滤波后的结果。
                raw_prediction = self.pose_estimator.estimate(frame, frame_index)
                prediction = self.pose_filter.update(raw_prediction)
                mocap_pose = self._compute_mocap_pose(frame.timestamp_s)
                backend_debug = self.yolo_backend.get_debug_state()
                result = PipelineResult(
                    frame_index=frame_index,
                    timestamp_s=frame.timestamp_s,
                    raw_prediction=raw_prediction,
                    prediction=prediction,
                    mocap_pose=mocap_pose,
                    backend_debug=backend_debug,
                )
                self._update_runtime_stats()
                self._write_result(result)
                self._print_result(result)
                self._show_result(frame, result)
                frame_index += 1

        except StopIteration:
            return None
        finally:
            # 确保相机和 CSV 文件在异常或 Esc 退出时也能释放。
            self.frame_source.stop()
            if self._csv_file is not None:
                self._csv_file.close()

    def _update_runtime_stats(self) -> None:
        """用指数滑动平均计算显示用 FPS，避免 HUD 数字大幅跳动。"""
        now_s = time.perf_counter()
        if self._last_perf_counter_s is not None:
            dt_s = max(now_s - self._last_perf_counter_s, 1e-6)
            fps = 1.0 / dt_s
            if self._smoothed_fps is None:
                self._smoothed_fps = fps
            else:
                self._smoothed_fps = self._smoothed_fps * 0.85 + fps * 0.15
        self._last_perf_counter_s = now_s
        return None

    def _print_result(self, result: PipelineResult) -> None:
        """按 JSON Lines 打印单帧结果，方便终端记录和后处理。"""
        if not self.config.output.print_json_lines:
            return None

        payload = {
            "frame_index": result.frame_index,
            "timestamp_s": result.timestamp_s,
            "prediction": None,
            "mocap_pose": None,
            "debug": result.backend_debug,
        }

        if result.prediction is not None:
            pose = result.prediction.pose
            payload["prediction"] = {
                "label": result.prediction.detection_label,
                "confidence": result.prediction.confidence,
                "reprojection_error_px": result.prediction.reprojection_error_px,
                "translation_m": pose.translation_m.tolist(),
                "quaternion_xyzw": matrix_to_quaternion(pose.rotation).tolist(),
                "source": result.prediction.source,
            }

        if result.mocap_pose is not None:
            payload["mocap_pose"] = {
                "translation_m": result.mocap_pose.translation_m.tolist(),
                "quaternion_xyzw": matrix_to_quaternion(result.mocap_pose.rotation).tolist(),
            }

        print(json.dumps(payload, ensure_ascii=False))
        return None

    def _draw_pose_hud(self, canvas: np.ndarray, result: PipelineResult) -> np.ndarray:
        """在预览窗口左上角绘制当前帧状态、位姿和后端调试信息。"""
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("opencv-python is required for visualization.") from exc

        panel_lines = [f"frame: {result.frame_index}", f"t: {result.timestamp_s:.3f}s"]
        if self._smoothed_fps is not None:
            panel_lines.append(f"fps: {self._smoothed_fps:.1f}")

        mode = result.backend_debug.get("mode")
        if mode:
            panel_lines.append(f"infer mode: {mode}")
        roi_xyxy = result.backend_debug.get("roi_xyxy")
        if roi_xyxy is not None:
            x1, y1, x2, y2 = [int(round(v)) for v in roi_xyxy]
            panel_lines.append(f"roi px: {x2 - x1}x{y2 - y1}")

        if result.prediction is not None:
            pose = result.prediction.pose
            roll_deg, pitch_deg, yaw_deg = matrix_to_euler_xyz_deg(pose.rotation)
            tx, ty, tz = pose.translation_m.tolist()
            panel_lines.extend(
                [
                    f"pred xyz(m): {tx:+.3f} {ty:+.3f} {tz:+.3f}",
                    f"pred rpy(deg): {roll_deg:+.1f} {pitch_deg:+.1f} {yaw_deg:+.1f}",
                    f"pred conf: {result.prediction.confidence:.3f}",
                    f"pred reproj(px): {result.prediction.reprojection_error_px:.2f}",
                    f"pred source: {result.prediction.source}",
                ]
            )
        else:
            panel_lines.append("pred: none")

        if result.mocap_pose is not None:
            roll_deg, pitch_deg, yaw_deg = matrix_to_euler_xyz_deg(result.mocap_pose.rotation)
            tx, ty, tz = result.mocap_pose.translation_m.tolist()
            panel_lines.extend(
                [
                    f"gt xyz(m):   {tx:+.3f} {ty:+.3f} {tz:+.3f}",
                    f"gt rpy(deg): {roll_deg:+.1f} {pitch_deg:+.1f} {yaw_deg:+.1f}",
                ]
            )

        padding = 10
        line_height = 24
        panel_width = 460
        panel_height = padding * 2 + line_height * len(panel_lines)
        overlay = canvas.copy()
        cv2.rectangle(overlay, (10, 10), (10 + panel_width, 10 + panel_height), (20, 20, 20), -1)
        canvas = cv2.addWeighted(overlay, 0.60, canvas, 0.40, 0)

        y = 10 + padding + 16
        for line in panel_lines:
            cv2.putText(
                canvas,
                line,
                (20, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.58,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            y += line_height

        return canvas

    def _draw_backend_debug(self, canvas: np.ndarray, result: PipelineResult) -> np.ndarray:
        """绘制 ROI 等后端调试框。"""
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("opencv-python is required for visualization.") from exc

        roi_xyxy = result.backend_debug.get("roi_xyxy")
        if roi_xyxy is not None:
            x1, y1, x2, y2 = [int(round(v)) for v in roi_xyxy]
            cv2.rectangle(canvas, (x1, y1), (x2, y2), (255, 255, 0), 1)
        return canvas

    def _show_result(self, frame: ImageFrame, result: PipelineResult) -> None:
        """按配置显示 OpenCV 窗口，并叠加预测和 Mocap GT。"""
        if not self.config.output.show_window:
            return None

        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("opencv-python is required for visualization.") from exc

        canvas = frame.color.copy()
        canvas = self._draw_backend_debug(canvas, result)
        if result.prediction is not None:
            canvas = draw_pose_overlay(
                image_bgr=canvas,
                object_points_xyz=self.object_points_xyz,
                pose_camera_object=result.prediction.pose,
                intrinsics=frame.intrinsics,
                color_bgr=(0, 255, 0),
                label="YOLO6D",
                edges=self.object_edges,
            )

        if result.mocap_pose is not None:
            canvas = draw_pose_overlay(
                image_bgr=canvas,
                object_points_xyz=self.object_points_xyz,
                pose_camera_object=result.mocap_pose,
                intrinsics=frame.intrinsics,
                color_bgr=(0, 165, 255),
                label="Mocap GT",
                edges=self.object_edges,
            )

        canvas = self._draw_pose_hud(canvas, result)
        cv2.imshow("YOLO6D Car Pose", canvas)
        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            raise StopIteration
        return None


def parse_args() -> argparse.Namespace:
    """pipeline 模块直接运行时使用的最小 CLI。"""
    parser = argparse.ArgumentParser(description="Run YOLO6D car pose pipeline.")
    parser.add_argument("--config", required=True, help="Path to YAML config file.")
    parser.add_argument("--max-frames", type=int, default=None, help="Maximum number of frames to process.")
    return parser.parse_args()


def main() -> None:
    """加载 YAML 并启动 PosePipeline。"""
    args = parse_args()
    config = load_config(args.config)
    pipeline = PosePipeline(config)
    pipeline.run(max_frames=args.max_frames)


if __name__ == "__main__":
    main()





