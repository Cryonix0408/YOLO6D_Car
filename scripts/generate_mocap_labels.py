"""结合图像、Mocap 和外参自动生成 YOLO Pose 标签。"""

from __future__ import annotations

# 读代码提示：
# 本脚本属于 labeling 阶段，把“图像 + FzMotion 刚体位姿 + 相机内参 + 小车 3D keypoints”
# 投影成 YOLO Pose 的 2D keypoint 标签。最容易出错的是坐标系和时间同步：
# camera rigid -> camera optical、object rigid -> car model、image timestamp -> mocap timestamp。
# 生成标签后必须先用 visualize_auto_labels.py 看 overlay，再进入训练。

import argparse
import csv
import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
# 支持从项目根目录直接执行脚本，而不必先安装 yolo6d_car 包。
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    import cv2
except ImportError as exc:
    raise RuntimeError("opencv-python is required for mocap label generation.") from exc

from yolo6d_car.config import ProjectConfig, load_config
from yolo6d_car.mocap.csv_provider import CSVRigidBodyProvider
from yolo6d_car.object_model import build_object_edges, build_object_keypoints
from yolo6d_car.path_utils import load_local_paths, resolve_path
from yolo6d_car.pose.pnp import project_points
from yolo6d_car.transforms import compose_poses, invert_pose, matrix_to_quaternion, pose_from_matrix, transform_points
from yolo6d_car.types import CameraIntrinsics, PoseSE3
from yolo6d_car.visualization import draw_pose_overlay


def _log_status(message: str) -> None:
    """统一自动标注脚本的日志前缀，方便从长日志里过滤。"""
    print(f"[generate_mocap_labels] {message}", flush=True)


def _log_progress(processed: int, total: int, counts: Counter, start_time_s: float) -> None:
    """周期性打印处理速度和跳过原因统计。"""
    elapsed_s = max(time.monotonic() - start_time_s, 1e-6)
    rate = processed / elapsed_s
    _log_status(
        "Processing "
        f"{processed}/{total} | "
        f"saved={counts.get('saved_labels', 0)} | "
        f"missing_mocap={counts.get('skip_missing_mocap', 0)} | "
        f"too_few_kpts={counts.get('skip_too_few_inframe_keypoints', 0)} | "
        f"invalid_bbox={counts.get('skip_invalid_bbox', 0)} | "
        f"elapsed={elapsed_s:.1f}s | "
        f"rate={rate:.1f} samples/s"
    )

def parse_args() -> argparse.Namespace:
    """定义自动标注参数；支持临时覆盖模型尺寸、刚体偏置和时间偏置。"""
    parser = argparse.ArgumentParser(description="Generate mocap-assisted 2D keypoint labels for car images.")
    parser.add_argument("--config", required=True, help="Path to the project YAML config.")
    parser.add_argument("--paths-config", default=None, help="Optional local paths YAML, e.g. configs/paths_local.yaml.")
    parser.add_argument("--validate-config", action="store_true", help="Validate config and paths without reading capture data or mocap CSV.")
    parser.add_argument("--samples-dir", default=None, help="Capture directory containing images/, samples.csv and intrinsics.json.")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to store generated labels. Defaults to outputs/auto_labels/<samples-dir-name>.",
    )
    parser.add_argument(
        "--csv-path",
        default=None,
        help="Optional mocap CSV override for this session. If set, it overrides mocap.csv_path from the project config.",
    )
    parser.add_argument(
        "--time-offset-s",
        type=float,
        default=None,
        help="Optional mocap time offset override in seconds. Positive means using a later mocap timestamp than the image timestamp.",
    )
    parser.add_argument(
        "--class-id",
        type=int,
        default=0,
        help="YOLO pose class id written into txt labels.",
    )
    parser.add_argument(
        "--min-inframe-keypoints",
        type=int,
        default=4,
        help="Minimum number of projected keypoints that must fall inside the image to keep a frame.",
    )
    parser.add_argument(
        "--save-overlays",
        action="store_true",
        help="Save overlay images for quick visual QA.",
    )
    parser.add_argument(
        "--dimensions-m",
        nargs=3,
        type=float,
        default=None,
        metavar=("L", "W", "H"),
        help="Temporarily override symmetric object dimensions in meters as length width height.",
    )
    parser.add_argument(
        "--object-extents-m",
        nargs=6,
        type=float,
        default=None,
        metavar=("XMIN", "XMAX", "YMIN", "YMAX", "ZMIN", "ZMAX"),
        help="Temporarily override an asymmetric cuboid using [x_min, x_max, y_min, y_max, z_min, z_max] in meters.",
    )
    parser.add_argument(
        "--object-translation-m",
        nargs=3,
        type=float,
        default=None,
        metavar=("TX", "TY", "TZ"),
        help="Temporarily override T_object_rigid_to_model translation in meters.",
    )
    parser.add_argument(
        "--object-rpy-deg",
        nargs=3,
        type=float,
        default=None,
        metavar=("ROLL", "PITCH", "YAW"),
        help="Temporarily override T_object_rigid_to_model rotation in degrees.",
    )
    return parser.parse_args()


def validate_label_config(args: argparse.Namespace) -> None:
    """Validate label-generation config without reading large data."""
    local_paths = load_local_paths(args.paths_config) if args.paths_config else None
    config = load_config(args.config, paths_config=args.paths_config)
    samples_dir = resolve_path(args.samples_dir, project_root=ROOT, local_paths=local_paths).resolve() if args.samples_dir else None
    output_dir = (
        resolve_path(args.output_dir, project_root=ROOT, local_paths=local_paths).resolve()
        if args.output_dir
        else None
    )
    payload = {
        "status": "ok",
        "script": Path(__file__).name,
        "config": str(Path(args.config).resolve()),
        "paths_config": None if args.paths_config is None else str(Path(args.paths_config).resolve()),
        "mocap_csv": None if config.mocap.csv_path is None else str(config.mocap.csv_path),
        "samples_dir": None if samples_dir is None else str(samples_dir),
        "samples_dir_exists": None if samples_dir is None else samples_dir.exists(),
        "output_dir": None if output_dir is None else str(output_dir),
        "object_model": config.object_model.keypoints_mode,
        "hardware_required": False,
        "large_data_required": False,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _default_output_dir(samples_dir: Path, paths_config: str | None = None) -> Path:
    """默认把标签写到 outputs/auto_labels/<session_name>。"""
    if paths_config:
        return load_local_paths(paths_config).outputs_root / "auto_labels" / samples_dir.name
    return ROOT / "outputs" / "auto_labels" / samples_dir.name


def _load_intrinsics(path: Path) -> CameraIntrinsics:
    """读取采集时保存的 RealSense 彩色相机内参。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    return CameraIntrinsics(
        fx=float(data["fx"]),
        fy=float(data["fy"]),
        cx=float(data["cx"]),
        cy=float(data["cy"]),
        width=int(data["width"]),
        height=int(data["height"]),
        dist_coeffs=np.asarray(data["dist_coeffs"], dtype=np.float64),
    )


def _parse_fzmotion_start_time(text: str) -> datetime | None:
    """解析 FzMotion CSV 元数据中的 StartTime 字段。"""
    text = (text or "").strip()
    if not text:
        return None
    for fmt in ("%Y.%m.%d %H:%M:%S:%f", "%Y.%m.%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None


def _resolve_sample_timestamp_s(row: dict[str, str], mocap_start_dt: datetime | None) -> tuple[float, str]:
    """把 samples.csv 的时间字段转换到 Mocap CSV 的相对秒时间轴。"""
    saved_local_time = (row.get("saved_local_time") or "").strip()
    if saved_local_time and mocap_start_dt is not None:
        try:
            sample_dt = datetime.fromisoformat(saved_local_time)
            return (sample_dt - mocap_start_dt).total_seconds(), "saved_local_time"
        except ValueError:
            pass

    saved_unix = (row.get("saved_unix_time_s") or "").strip()
    if saved_unix and mocap_start_dt is not None:
        try:
            sample_dt = datetime.fromtimestamp(float(saved_unix))
            return (sample_dt - mocap_start_dt).total_seconds(), "saved_unix_time_s"
        except ValueError:
            pass

    return float(row["device_timestamp_s"]), "device_timestamp_s"


def _rpy_deg_to_matrix(roll_deg: float, pitch_deg: float, yaw_deg: float) -> np.ndarray:
    """把命令行传入的 RPY 欧拉角覆盖值转换为旋转矩阵。"""
    roll = np.deg2rad(roll_deg)
    pitch = np.deg2rad(pitch_deg)
    yaw = np.deg2rad(yaw_deg)

    cx, sx = np.cos(roll), np.sin(roll)
    cy, sy = np.cos(pitch), np.sin(pitch)
    cz, sz = np.cos(yaw), np.sin(yaw)

    rx = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, cx, -sx],
            [0.0, sx, cx],
        ],
        dtype=np.float64,
    )
    ry = np.array(
        [
            [cy, 0.0, sy],
            [0.0, 1.0, 0.0],
            [-sy, 0.0, cy],
        ],
        dtype=np.float64,
    )
    rz = np.array(
        [
            [cz, -sz, 0.0],
            [sz, cz, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    return rz @ ry @ rx


def _effective_object_rigid_to_model(config: ProjectConfig, args: argparse.Namespace) -> PoseSE3:
    """合成最终使用的 T_object_rigid_to_model，允许命令行临时覆盖。"""
    translation_m = config.mocap.object_rigid_to_model.translation_m.copy()
    rotation = config.mocap.object_rigid_to_model.rotation.copy()

    if args.object_translation_m is not None:
        translation_m = np.asarray(args.object_translation_m, dtype=np.float64)

    if args.object_rpy_deg is not None:
        rotation = _rpy_deg_to_matrix(*args.object_rpy_deg)

    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = rotation
    matrix[:3, 3] = translation_m
    return pose_from_matrix(
        parent_frame=config.mocap.object_rigid_body,
        child_frame=config.mocap.object_model_frame,
        matrix=matrix,
    )


def _effective_object_model_config(config: ProjectConfig, args: argparse.Namespace) -> dict:
    """确定本次投影使用的 3D 关键点模型配置。"""
    model_config = {
        "keypoints_mode": config.object_model.keypoints_mode,
        "include_center": config.object_model.include_center,
    }

    if args.object_extents_m is not None:
        # 调参时可不用改 JSON/YAML，直接用命令行切换非对称包围盒。
        model_config["keypoints_mode"] = "extents_cuboid"
        model_config["extents_m"] = tuple(float(v) for v in args.object_extents_m)
        return model_config

    if args.dimensions_m is not None:
        # 简单长方体模型用于快速检查外参或粗标注。
        model_config["keypoints_mode"] = "cuboid"
        model_config["dimensions_m"] = tuple(float(v) for v in args.dimensions_m)
        return model_config

    mode = config.object_model.keypoints_mode.lower()
    if mode in {"extents_cuboid", "asymmetric_cuboid"} and config.object_model.extents_m is not None:
        model_config["extents_m"] = config.object_model.extents_m
    elif mode == "custom" and config.object_model.model_json_path is not None:
        model_config["model_json_path"] = str(config.object_model.model_json_path)
    else:
        model_config["dimensions_m"] = config.object_model.dimensions_m

    return model_config


def _world_camera_optical_pose(
    config: ProjectConfig,
    provider: CSVRigidBodyProvider,
    timestamp_s: float,
) -> PoseSE3 | None:
    """计算 T_world_camera_optical；优先用静态配置，否则由相机刚体外参推得。"""
    mocap_timestamp_s = timestamp_s + config.mocap.time_offset_s

    if config.mocap.world_camera_optical is not None:
        # 固定相机模式下，世界到相机光学坐标系可以直接写死在 YAML 里。
        static_pose = config.mocap.world_camera_optical
        return PoseSE3(
            parent_frame=static_pose.parent_frame,
            child_frame=static_pose.child_frame,
            rotation=static_pose.rotation.copy(),
            translation_m=static_pose.translation_m.copy(),
            timestamp_s=timestamp_s,
        )

    if config.mocap.camera_rigid_body is None or config.mocap.camera_rigid_to_optical is None:
        return None

    # 动捕给的是世界到相机刚体，乘上相机刚体到光学坐标系外参。
    camera_rigid_pose = provider.get_pose(
        rigid_body=config.mocap.camera_rigid_body,
        timestamp_s=mocap_timestamp_s,
        max_time_diff_s=config.mocap.max_time_diff_s,
    )
    if camera_rigid_pose is None:
        return None

    return compose_poses(camera_rigid_pose, config.mocap.camera_rigid_to_optical)


def _camera_object_pose(
    config: ProjectConfig,
    provider: CSVRigidBodyProvider,
    timestamp_s: float,
    object_rigid_to_model: PoseSE3,
) -> PoseSE3 | None:
    """计算最终投影所需的 T_camera_optical_object_model。"""
    world_camera_optical = _world_camera_optical_pose(config, provider, timestamp_s)
    if world_camera_optical is None:
        return None

    mocap_timestamp_s = timestamp_s + config.mocap.time_offset_s
    object_rigid_pose = provider.get_pose(
        rigid_body=config.mocap.object_rigid_body,
        timestamp_s=mocap_timestamp_s,
        max_time_diff_s=config.mocap.max_time_diff_s,
    )
    if object_rigid_pose is None:
        return None

    # 坐标链：camera <- world <- object_rigid <- object_model。
    world_object_model = compose_poses(object_rigid_pose, object_rigid_to_model)
    camera_optical_world = invert_pose(world_camera_optical)
    return compose_poses(camera_optical_world, world_object_model)


def _compute_bbox_xyxy(projected_px: np.ndarray, in_frame_mask: np.ndarray, width: int, height: int) -> list[float] | None:
    """根据落在图像内的关键点生成像素 bbox。"""
    if not np.any(in_frame_mask):
        return None

    points = projected_px[in_frame_mask]
    x0 = float(np.clip(np.min(points[:, 0]), 0.0, width - 1.0))
    y0 = float(np.clip(np.min(points[:, 1]), 0.0, height - 1.0))
    x1 = float(np.clip(np.max(points[:, 0]), 0.0, width - 1.0))
    y1 = float(np.clip(np.max(points[:, 1]), 0.0, height - 1.0))

    if x1 <= x0 or y1 <= y0:
        return None

    return [x0, y0, x1, y1]


def _bbox_to_yolo_xywh(bbox_xyxy: list[float], width: int, height: int) -> list[float]:
    """把像素 xyxy bbox 转成 YOLO 需要的归一化 cx/cy/w/h。"""
    x0, y0, x1, y1 = bbox_xyxy
    cx = ((x0 + x1) * 0.5) / width
    cy = ((y0 + y1) * 0.5) / height
    bw = (x1 - x0) / width
    bh = (y1 - y0) / height
    return [cx, cy, bw, bh]


def _keypoints_to_yolo(projected_px: np.ndarray, front_mask: np.ndarray, in_frame_mask: np.ndarray, width: int, height: int) -> list[float]:
    """把投影关键点转成 YOLO Pose 的 x/y/visibility 序列。"""
    values: list[float] = []
    for idx in range(projected_px.shape[0]):
        if front_mask[idx]:
            # 在相机前方但可能出画：出画点标为 visibility=1。
            x = float(np.clip(projected_px[idx, 0], 0.0, width - 1.0)) / width
            y = float(np.clip(projected_px[idx, 1], 0.0, height - 1.0)) / height
            visibility = 2 if in_frame_mask[idx] else 1
        else:
            # 在相机后方的点不可见，按 YOLO 约定写 0,0,0。
            x = 0.0
            y = 0.0
            visibility = 0
        values.extend([x, y, float(visibility)])
    return values


def _write_yolo_label(path: Path, class_id: int, bbox_xywh: list[float], keypoints_yolo: list[float]) -> None:
    """写一行 YOLO Pose 标签：class bbox keypoints。"""
    values = [float(class_id), *bbox_xywh, *keypoints_yolo]
    line = " ".join(f"{value:.6f}" for value in values)
    path.write_text(line + "\n", encoding="utf-8")


def main() -> None:
    """读取样本、动捕和外参，逐帧投影 3D 模型点并写 YOLO Pose 标签。"""
    args = parse_args()
    if args.validate_config:
        validate_label_config(args)
        return None
    if not args.samples_dir:
        raise SystemExit("--samples-dir is required unless --validate-config is used")
    run_start_s = time.monotonic()

    _log_status(f"Step 1/6 Loading config: {Path(args.config).resolve()}")
    config = load_config(args.config, paths_config=args.paths_config)
    if args.csv_path:
        config.mocap.csv_path = resolve_path(args.csv_path, project_root=ROOT, local_paths=load_local_paths(args.paths_config) if args.paths_config else None).resolve()
    if args.time_offset_s is not None:
        config.mocap.time_offset_s = float(args.time_offset_s)

    # 输出目录内同时保存 txt 标签、JSONL 详情、图片清单和可选 overlay。
    local_paths = load_local_paths(args.paths_config) if args.paths_config else None
    samples_dir = resolve_path(args.samples_dir, project_root=ROOT, local_paths=local_paths).resolve()
    output_dir = resolve_path(args.output_dir, project_root=ROOT, local_paths=local_paths).resolve() if args.output_dir else _default_output_dir(samples_dir, args.paths_config)
    labels_dir = output_dir / "labels_yolo_pose"
    overlays_dir = output_dir / "overlays"
    annotations_path = output_dir / "annotations.jsonl"
    summary_path = output_dir / "summary.json"
    image_list_path = output_dir / "images.txt"

    _log_status(f"Step 2/6 Preparing output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    if args.save_overlays:
        overlays_dir.mkdir(parents=True, exist_ok=True)

    _log_status(f"Step 3/6 Loading mocap CSV: {config.mocap.csv_path}")
    provider = CSVRigidBodyProvider(config.mocap.csv_path)
    mocap_start_dt = _parse_fzmotion_start_time(provider.metadata.get("StartTime", ""))

    _log_status(f"Step 4/6 Loading intrinsics and object model from: {samples_dir}")
    intrinsics = _load_intrinsics(samples_dir / "intrinsics.json")
    object_model_config = _effective_object_model_config(config, args)
    object_rigid_to_model = _effective_object_rigid_to_model(config, args)
    object_points_xyz = build_object_keypoints(object_model_config)
    object_edges = build_object_edges(object_model_config)

    _log_status(f"Step 5/6 Reading sample list: {samples_dir / 'samples.csv'}")
    with (samples_dir / "samples.csv").open("r", encoding="utf-8", newline="") as handle:
        sample_rows = list(csv.DictReader(handle))

    total_samples = len(sample_rows)
    progress_interval = max(1, min(50, total_samples // 20 if total_samples > 0 else 1))
    _log_status(
        f"Step 6/6 Starting label generation for {total_samples} samples | "
        f"save_overlays={args.save_overlays} | output={output_dir}"
    )

    counts = Counter()
    counts["total_rows"] = 0
    counts["saved_labels"] = 0

    with annotations_path.open("w", encoding="utf-8") as annotations_file, \
         image_list_path.open("w", encoding="utf-8") as image_list_file:

        for processed_index, row in enumerate(sample_rows, start=1):
            counts["total_rows"] += 1
            sample_index = int(row["sample_index"])
            image_path = (samples_dir / row["image_path"]).resolve()
            timestamp_s, timestamp_source = _resolve_sample_timestamp_s(row, mocap_start_dt)

            # 没有匹配到相机或物体 Mocap 位姿时，这一帧不能生成可靠标签。
            pose_camera_object = _camera_object_pose(config, provider, timestamp_s, object_rigid_to_model)
            if pose_camera_object is None:
                counts["skip_missing_mocap"] += 1
                if processed_index == 1 or processed_index % progress_interval == 0 or processed_index == total_samples:
                    _log_progress(processed_index, total_samples, counts, run_start_s)
                continue

            camera_points_xyz = transform_points(pose_camera_object, object_points_xyz)
            projected_px = project_points(object_points_xyz, pose_camera_object, intrinsics)

            # 只用有限、在相机前方、落在图像内的点计算 bbox 和保留条件。
            finite_mask = np.isfinite(projected_px).all(axis=1)
            front_mask = finite_mask & (camera_points_xyz[:, 2] > 1e-6)
            in_frame_mask = (
                front_mask
                & (projected_px[:, 0] >= 0.0)
                & (projected_px[:, 0] <= intrinsics.width - 1.0)
                & (projected_px[:, 1] >= 0.0)
                & (projected_px[:, 1] <= intrinsics.height - 1.0)
            )

            num_in_frame = int(np.sum(in_frame_mask))
            if num_in_frame < args.min_inframe_keypoints:
                counts["skip_too_few_inframe_keypoints"] += 1
                if processed_index == 1 or processed_index % progress_interval == 0 or processed_index == total_samples:
                    _log_progress(processed_index, total_samples, counts, run_start_s)
                continue

            bbox_xyxy = _compute_bbox_xyxy(projected_px, in_frame_mask, intrinsics.width, intrinsics.height)
            if bbox_xyxy is None:
                counts["skip_invalid_bbox"] += 1
                if processed_index == 1 or processed_index % progress_interval == 0 or processed_index == total_samples:
                    _log_progress(processed_index, total_samples, counts, run_start_s)
                continue

            bbox_xywh_yolo = _bbox_to_yolo_xywh(bbox_xyxy, intrinsics.width, intrinsics.height)
            keypoints_yolo = _keypoints_to_yolo(projected_px, front_mask, in_frame_mask, intrinsics.width, intrinsics.height)

            # txt 是 Ultralytics 训练输入；JSONL 保存完整投影和位姿，便于排查标签质量。
            label_path = labels_dir / f"{image_path.stem}.txt"
            _write_yolo_label(label_path, class_id=args.class_id, bbox_xywh=bbox_xywh_yolo, keypoints_yolo=keypoints_yolo)

            record = {
                "sample_index": sample_index,
                "image_path": str(image_path),
                "label_path": str(label_path),
                "timestamp_s": float(timestamp_s),
                "timestamp_source": timestamp_source,
                "bbox_xyxy_px": bbox_xyxy,
                "num_keypoints_total": int(object_points_xyz.shape[0]),
                "num_keypoints_in_frame": num_in_frame,
                "front_mask": front_mask.astype(int).tolist(),
                "in_frame_mask": in_frame_mask.astype(int).tolist(),
                "projected_keypoints_px": [[float(x), float(y)] for x, y in projected_px.tolist()],
                "camera_points_xyz_m": [[float(x), float(y), float(z)] for x, y, z in camera_points_xyz.tolist()],
                "pose_camera_object": {
                    "translation_m": [float(x) for x in pose_camera_object.translation_m.tolist()],
                    "quaternion_xyzw": [float(x) for x in matrix_to_quaternion(pose_camera_object.rotation).tolist()],
                    "matrix": [[float(v) for v in row_vals] for row_vals in pose_camera_object.as_matrix().tolist()],
                },
            }
            annotations_file.write(json.dumps(record, ensure_ascii=False) + "\n")
            image_list_file.write(str(image_path) + "\n")
            counts["saved_labels"] += 1

            if args.save_overlays:
                # overlay 是人工抽查最直观的产物，训练时不会读取它。
                image_bgr = cv2.imread(str(image_path))
                if image_bgr is not None:
                    overlay = draw_pose_overlay(
                        image_bgr=image_bgr,
                        object_points_xyz=object_points_xyz,
                        pose_camera_object=pose_camera_object,
                        intrinsics=intrinsics,
                        color_bgr=(0, 255, 0),
                        label="Mocap GT",
                        edges=object_edges,
                    )
                    cv2.putText(
                        overlay,
                        f"sample={sample_index} in_frame={num_in_frame}",
                        (16, 32),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 255),
                        2,
                        cv2.LINE_AA,
                    )
                    cv2.imwrite(str(overlays_dir / image_path.name), overlay)

            if processed_index == 1 or processed_index % progress_interval == 0 or processed_index == total_samples:
                _log_progress(processed_index, total_samples, counts, run_start_s)

    _log_status("Writing summary.json and finishing up")
    summary = {
        "config": str(Path(args.config).resolve()),
        "samples_dir": str(samples_dir),
        "csv_path": str(config.mocap.csv_path.resolve()),
        "output_dir": str(output_dir),
        "intrinsics": {
            "width": intrinsics.width,
            "height": intrinsics.height,
            "fx": intrinsics.fx,
            "fy": intrinsics.fy,
            "cx": intrinsics.cx,
            "cy": intrinsics.cy,
        },
        "object_model_config": object_model_config,
        "object_rigid_to_model": {
            "translation_m": [float(x) for x in object_rigid_to_model.translation_m.tolist()],
            "quaternion_xyzw": [float(x) for x in matrix_to_quaternion(object_rigid_to_model.rotation).tolist()],
        },
        "counts": dict(counts),
        "timestamp_mode": "saved_local_time if available else fallback",
        "min_inframe_keypoints": int(args.min_inframe_keypoints),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _log_status("Done")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

