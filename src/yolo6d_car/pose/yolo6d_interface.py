"""关键点检测后端、ROI 跟踪与 PnP 入口封装。"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

from ..config import PnPConfig, ROITrackerConfig
from ..types import ImageFrame, KeypointDetection, PoseEstimate
from .pnp import solve_pose_from_detection


class YOLO6DBackend(ABC):
    """所有关键点检测后端的最小接口。"""

    @abstractmethod
    def predict(self, frame: ImageFrame, frame_index: int) -> list[KeypointDetection]:
        """输入一帧图像，输出 2D 关键点检测列表。"""
        raise NotImplementedError

    def get_debug_state(self) -> dict[str, object]:
        """返回可选调试信息，例如 ROI、模式和丢帧计数。"""
        return {}


class JSONReplayBackend(YOLO6DBackend):
    """从离线 JSON 文件回放关键点检测结果。"""

    def __init__(self, json_path: str | Path, timestamp_tolerance_s: float = 0.05) -> None:
        self.json_path = Path(json_path)
        if not self.json_path.exists():
            raise FileNotFoundError(f"Replay JSON not found: {self.json_path}")

        self.timestamp_tolerance_s = timestamp_tolerance_s
        self._frames_by_index: dict[int, list[KeypointDetection]] = {}
        self._frames_by_timestamp: list[tuple[float, list[KeypointDetection]]] = []
        self._load_json()

    def _load_json(self) -> None:
        """读取 JSONReplay 格式，并建立按帧号和按时间戳查询的索引。"""
        with self.json_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        for raw_frame in payload.get("frames", []):
            detections = []
            for raw_detection in raw_frame.get("detections", []):
                detections.append(
                    KeypointDetection(
                        label=str(raw_detection["label"]),
                        confidence=float(raw_detection["confidence"]),
                        image_points_px=np.asarray(raw_detection["image_points_px"], dtype=np.float64),
                        keypoint_scores=(
                            None
                            if raw_detection.get("keypoint_scores") is None
                            else np.asarray(raw_detection["keypoint_scores"], dtype=np.float64)
                        ),
                        bbox_xyxy=(
                            None
                            if raw_detection.get("bbox_xyxy") is None
                            else np.asarray(raw_detection["bbox_xyxy"], dtype=np.float64)
                        ),
                        inference_mode=str(raw_detection.get("inference_mode", "replay")),
                    )
                )

            if "frame_index" in raw_frame:
                self._frames_by_index[int(raw_frame["frame_index"])] = detections

            if "timestamp_s" in raw_frame:
                self._frames_by_timestamp.append((float(raw_frame["timestamp_s"]), detections))

        self._frames_by_timestamp.sort(key=lambda item: item[0])

    def predict(self, frame: ImageFrame, frame_index: int) -> list[KeypointDetection]:
        """优先按 frame_index 命中；否则按时间戳容差找最近帧。"""
        if frame_index in self._frames_by_index:
            return self._frames_by_index[frame_index]

        best_detections: list[KeypointDetection] = []
        best_delta = None
        for timestamp_s, detections in self._frames_by_timestamp:
            delta = abs(timestamp_s - frame.timestamp_s)
            if delta <= self.timestamp_tolerance_s and (best_delta is None or delta < best_delta):
                best_delta = delta
                best_detections = detections

        return best_detections


class UltralyticsLiveBackend(YOLO6DBackend):
    """基于 Ultralytics YOLO Pose 的实时检测后端，带可选 ROI 跟踪。"""

    def __init__(
        self,
        model_path: str | Path,
        label: str,
        roi_tracker: ROITrackerConfig,
        conf_threshold: float = 0.25,
        imgsz: int = 640,
        device: str = "",
    ) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "Ultralytics is required for backend 'ultralytics_live'. Install it with: python -m pip install ultralytics"
            ) from exc

        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Ultralytics model not found: {self.model_path}")

        self.label = label
        self.conf_threshold = conf_threshold
        self.imgsz = imgsz
        self.device = device
        self.roi_tracker = roi_tracker
        self._model = YOLO(str(self.model_path))
        self._last_bbox_xyxy: np.ndarray | None = None
        self._last_bbox_frame_index: int | None = None
        self._last_roi_xyxy: np.ndarray | None = None
        self._last_mode: str = "full"
        self._missed_frames: int = 0
        self._bbox_velocity_px_per_frame: np.ndarray | None = None

    def get_debug_state(self) -> dict[str, object]:
        """把 ROI 跟踪内部状态暴露给 HUD/日志。"""
        return {
            "mode": self._last_mode,
            "roi_xyxy": None if self._last_roi_xyxy is None else self._last_roi_xyxy.tolist(),
            "bbox_xyxy": None if self._last_bbox_xyxy is None else self._last_bbox_xyxy.tolist(),
            "bbox_velocity_px_per_frame": (
                None if self._bbox_velocity_px_per_frame is None else self._bbox_velocity_px_per_frame.tolist()
            ),
            "predict_motion": self.roi_tracker.predict_motion,
            "missed_frames": self._missed_frames,
        }

    def predict(self, frame: ImageFrame, frame_index: int) -> list[KeypointDetection]:
        """根据 ROI 状态选择全图、ROI 或 fallback 全图推理。"""
        if not self.roi_tracker.enabled:
            detections = self._predict_image(frame.color, offset_xy=(0, 0), inference_mode="full")
            self._update_tracking_state(detections, mode="full", frame_index=frame_index)
            return detections

        should_run_full = (
            self._last_bbox_xyxy is None
            or self.roi_tracker.full_frame_interval <= 0
            or frame_index % self.roi_tracker.full_frame_interval == 0
        )
        if not should_run_full:
            missed_limit = (
                self.roi_tracker.max_prediction_frames
                if self.roi_tracker.predict_motion
                else self.roi_tracker.max_missed_frames
            )
            should_run_full = self._missed_frames > missed_limit

        if should_run_full:
            # 周期性全图检测用于纠正 ROI 漂移。
            detections = self._predict_image(frame.color, offset_xy=(0, 0), inference_mode="full")
            self._update_tracking_state(detections, mode="full", frame_index=frame_index)
            return detections

        tracking_bbox = self._predict_tracking_bbox(frame_index)
        if tracking_bbox is None:
            detections = self._predict_image(frame.color, offset_xy=(0, 0), inference_mode="fallback_full")
            self._update_tracking_state(detections, mode="fallback_full", frame_index=frame_index)
            return detections

        roi_xyxy = self._compute_expanded_roi(tracking_bbox, frame.color.shape)
        self._last_roi_xyxy = roi_xyxy
        x1, y1, x2, y2 = roi_xyxy.astype(int).tolist()
        crop = frame.color[y1:y2, x1:x2]
        if crop.size == 0:
            # ROI 裁剪异常时退回全图，保证实时链路尽量不断。
            detections = self._predict_image(frame.color, offset_xy=(0, 0), inference_mode="fallback_full")
            self._update_tracking_state(detections, mode="fallback_full", frame_index=frame_index)
            return detections

        detections = self._predict_image(crop, offset_xy=(x1, y1), inference_mode="roi")
        if detections:
            self._update_tracking_state(detections, mode="roi", frame_index=frame_index)
            return detections

        # ROI 没检到时再跑一次全图，避免目标快速运动时被裁掉后持续丢失。
        detections = self._predict_image(frame.color, offset_xy=(0, 0), inference_mode="fallback_full")
        self._update_tracking_state(detections, mode="fallback_full", frame_index=frame_index)
        return detections

    def _predict_image(
        self,
        image_bgr: np.ndarray,
        offset_xy: tuple[int, int],
        inference_mode: str,
    ) -> list[KeypointDetection]:
        """对整图或裁剪图运行 Ultralytics，并把坐标补回原图坐标系。"""
        offset_x, offset_y = offset_xy
        results = self._model.predict(
            source=image_bgr,
            imgsz=self.imgsz,
            device=self.device,
            conf=self.conf_threshold,
            verbose=False,
        )
        result = results[0]

        detections: list[KeypointDetection] = []
        boxes = getattr(result, "boxes", None)
        keypoints = getattr(result, "keypoints", None)
        if boxes is None or keypoints is None or len(boxes) == 0:
            return detections

        image_points = keypoints.xy.cpu().numpy()
        keypoint_scores = None
        if getattr(keypoints, "conf", None) is not None:
            keypoint_scores = keypoints.conf.cpu().numpy()

        boxes_conf = boxes.conf.cpu().numpy() if getattr(boxes, "conf", None) is not None else None
        boxes_xyxy = boxes.xyxy.cpu().numpy() if getattr(boxes, "xyxy", None) is not None else None
        count = min(len(image_points), len(boxes))
        for idx in range(count):
            confidence = 1.0 if boxes_conf is None else float(boxes_conf[idx])
            if confidence < self.conf_threshold:
                continue

            bbox_xyxy = None
            if boxes_xyxy is not None:
                # ROI 推理时 Ultralytics 返回裁剪图坐标，需要加上裁剪偏移。
                bbox_xyxy = np.asarray(boxes_xyxy[idx], dtype=np.float64).copy()
                bbox_xyxy[[0, 2]] += offset_x
                bbox_xyxy[[1, 3]] += offset_y

            points = np.asarray(image_points[idx], dtype=np.float64).copy()
            points[:, 0] += offset_x
            points[:, 1] += offset_y
            detections.append(
                KeypointDetection(
                    label=self.label,
                    confidence=confidence,
                    image_points_px=points,
                    keypoint_scores=(
                        None
                        if keypoint_scores is None
                        else np.asarray(keypoint_scores[idx], dtype=np.float64)
                    ),
                    bbox_xyxy=bbox_xyxy,
                    inference_mode=inference_mode,
                )
            )

        return detections

    def _update_tracking_state(self, detections: list[KeypointDetection], mode: str, frame_index: int) -> None:
        """根据本帧检测结果更新 bbox、速度和丢帧状态。"""
        self._last_mode = mode
        if not detections:
            self._missed_frames += 1
            clear_after = self.roi_tracker.max_missed_frames
            if self.roi_tracker.predict_motion:
                clear_after = max(clear_after, self.roi_tracker.max_prediction_frames)
            if self._missed_frames > clear_after:
                # 连续丢失超过阈值后清空 ROI，下次回到全图检测。
                self._last_bbox_xyxy = None
                self._last_bbox_frame_index = None
                self._last_roi_xyxy = None
                self._bbox_velocity_px_per_frame = None
            return None

        best = max(detections, key=lambda det: det.confidence)
        bbox = best.bbox_xyxy
        if bbox is None:
            bbox = self._bbox_from_points(best.image_points_px)
        self._update_bbox_motion(bbox, frame_index)
        self._last_bbox_xyxy = bbox
        self._last_bbox_frame_index = frame_index
        if mode == "full":
            self._last_roi_xyxy = None
        self._missed_frames = 0
        return None

    def _update_bbox_motion(self, bbox_xyxy: np.ndarray, frame_index: int) -> None:
        """估计 bbox 像素速度，用于高速运动时预测下一帧 ROI。"""
        if not self.roi_tracker.predict_motion:
            self._bbox_velocity_px_per_frame = None
            return None

        bbox = np.asarray(bbox_xyxy, dtype=np.float64).reshape(4)
        if self._last_bbox_xyxy is None or self._last_bbox_frame_index is None:
            self._bbox_velocity_px_per_frame = np.zeros(4, dtype=np.float64)
            return None

        frame_delta = max(frame_index - self._last_bbox_frame_index, 1)
        measured_velocity = (bbox - self._last_bbox_xyxy) / float(frame_delta)
        alpha = float(np.clip(self.roi_tracker.velocity_alpha, 0.0, 1.0))
        if self._bbox_velocity_px_per_frame is None:
            self._bbox_velocity_px_per_frame = measured_velocity
        else:
            self._bbox_velocity_px_per_frame = (
                (1.0 - alpha) * self._bbox_velocity_px_per_frame + alpha * measured_velocity
            )
        return None

    def _predict_tracking_bbox(self, frame_index: int) -> np.ndarray | None:
        """按上一帧 bbox 和速度外推当前帧应裁剪的区域。"""
        if self._last_bbox_xyxy is None:
            return None
        if (
            not self.roi_tracker.predict_motion
            or self._bbox_velocity_px_per_frame is None
            or self._last_bbox_frame_index is None
        ):
            return self._last_bbox_xyxy

        frame_delta = max(frame_index - self._last_bbox_frame_index, 0)
        frame_delta = min(frame_delta, max(self.roi_tracker.max_prediction_frames, 0))
        return self._last_bbox_xyxy + self._bbox_velocity_px_per_frame * float(frame_delta)

    @staticmethod
    def _bbox_from_points(image_points_px: np.ndarray) -> np.ndarray:
        """在没有 detector bbox 时，用关键点外接框代替。"""
        points = np.asarray(image_points_px, dtype=np.float64).reshape(-1, 2)
        x_min = float(np.min(points[:, 0]))
        y_min = float(np.min(points[:, 1]))
        x_max = float(np.max(points[:, 0]))
        y_max = float(np.max(points[:, 1]))
        return np.array([x_min, y_min, x_max, y_max], dtype=np.float64)

    def _compute_expanded_roi(self, bbox_xyxy: np.ndarray, image_shape: tuple[int, ...]) -> np.ndarray:
        """把 bbox 按配置扩张并裁剪到图像范围内。"""
        height, width = image_shape[:2]
        x1, y1, x2, y2 = np.asarray(bbox_xyxy, dtype=np.float64).reshape(4)
        cx = (x1 + x2) * 0.5
        cy = (y1 + y2) * 0.5
        box_w = max(x2 - x1, float(self.roi_tracker.min_size_px))
        box_h = max(y2 - y1, float(self.roi_tracker.min_size_px))

        if self.roi_tracker.square_crop:
            side = max(box_w, box_h) * self.roi_tracker.expand_ratio
            box_w = side
            box_h = side
        else:
            box_w *= self.roi_tracker.expand_ratio
            box_h *= self.roi_tracker.expand_ratio

        roi_x1 = max(0.0, cx - box_w * 0.5)
        roi_y1 = max(0.0, cy - box_h * 0.5)
        roi_x2 = min(float(width), cx + box_w * 0.5)
        roi_y2 = min(float(height), cy + box_h * 0.5)

        if roi_x2 - roi_x1 < self.roi_tracker.min_size_px:
            deficit = self.roi_tracker.min_size_px - (roi_x2 - roi_x1)
            roi_x1 = max(0.0, roi_x1 - deficit * 0.5)
            roi_x2 = min(float(width), roi_x2 + deficit * 0.5)
        if roi_y2 - roi_y1 < self.roi_tracker.min_size_px:
            deficit = self.roi_tracker.min_size_px - (roi_y2 - roi_y1)
            roi_y1 = max(0.0, roi_y1 - deficit * 0.5)
            roi_y2 = min(float(height), roi_y2 + deficit * 0.5)

        return np.array([roi_x1, roi_y1, roi_x2, roi_y2], dtype=np.float64)


class YOLO6DPoseEstimator:
    """把检测后端输出的 2D 关键点转换成 6DoF PoseEstimate。"""

    def __init__(
        self,
        backend: YOLO6DBackend,
        object_points_xyz: np.ndarray,
        conf_threshold: float,
        pnp_config: PnPConfig,
    ) -> None:
        self.backend = backend
        self.object_points_xyz = np.asarray(object_points_xyz, dtype=np.float64)
        self.conf_threshold = conf_threshold
        self.pnp_config = pnp_config

    def estimate(self, frame: ImageFrame, frame_index: int) -> PoseEstimate | None:
        """对一帧图像取最佳检测，并用 PnP 解算位姿。"""
        detections = self.backend.predict(frame, frame_index)
        best_estimate = None

        for detection in detections:
            if detection.confidence < self.conf_threshold:
                continue

            estimate = solve_pose_from_detection(
                detection=detection,
                object_points_xyz=self.object_points_xyz,
                intrinsics=frame.intrinsics,
                pnp_config=self.pnp_config,
            )
            if estimate is None:
                continue

            # source 字段保留 full/roi/fallback 信息，便于分析实时效果。
            estimate.source = f"{estimate.source}:{detection.inference_mode}"
            if best_estimate is None or estimate.confidence > best_estimate.confidence:
                best_estimate = estimate

        return best_estimate

