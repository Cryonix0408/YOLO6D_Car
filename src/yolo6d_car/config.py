"""项目 YAML 配置加载与强类型配置对象定义。"""

from __future__ import annotations

# 读代码提示：
# 本模块是“配置入口”，负责把 YAML 中的 camera/mocap/object_model/yolo6d/output
# 转成 dataclass。它不会采集、训练或推理，但后续 pipeline 的路径、内参、刚体名
# 都来自这里。若某个脚本路径解析到了错误磁盘，优先检查本模块和 path_utils.py。

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

from .path_utils import LocalPaths, load_local_paths, resolve_path
from .transforms import pose_from_quaternion_translation
from .types import PoseSE3


@dataclass(slots=True)
class CameraConfig:
    """相机基础配置。"""

    source: str
    color_width: int
    color_height: int
    fps: int
    enable_depth: bool
    align_depth_to_color: bool


@dataclass(slots=True)
class MocapConfig:
    """动捕输入和坐标系对齐相关配置。"""

    enabled: bool
    mode: str
    csv_path: Path | None
    camera_rigid_body: str | None
    object_rigid_body: str
    max_time_diff_s: float
    time_offset_s: float
    camera_optical_frame: str
    object_model_frame: str
    camera_rigid_to_optical: PoseSE3 | None
    world_camera_optical: PoseSE3 | None
    object_rigid_to_model: PoseSE3


@dataclass(slots=True)
class ObjectModelConfig:
    """小车 3D 模型点配置。"""

    label: str
    keypoints_mode: str
    dimensions_m: tuple[float, float, float] | None
    extents_m: tuple[float, float, float, float, float, float] | None
    model_json_path: Path | None
    include_center: bool


@dataclass(slots=True)
class PnPConfig:
    """PnP 求解参数。"""

    ransac_reproj_threshold_px: float
    iterations_count: int
    confidence: float
    min_keypoint_score: float


@dataclass(slots=True)
class ROITrackerConfig:
    """ROI 跟踪参数。"""

    enabled: bool
    expand_ratio: float
    min_size_px: int
    full_frame_interval: int
    max_missed_frames: int
    square_crop: bool
    predict_motion: bool
    velocity_alpha: float
    max_prediction_frames: int


@dataclass(slots=True)
class TemporalFilterConfig:
    """时间滤波参数。"""

    enabled: bool
    translation_alpha: float
    rotation_alpha: float
    max_translation_jump_m: float
    max_angle_jump_deg: float
    hold_last_frames: int


@dataclass(slots=True)
class YOLO6DConfig:
    """检测、回放、ROI 和时间滤波的综合配置。"""

    backend: str
    conf_threshold: float
    replay_json_path: Path | None
    model_path: Path | None
    inference_imgsz: int
    inference_device: str
    replay_timestamp_tolerance_s: float
    roi_tracker: ROITrackerConfig
    temporal_filter: TemporalFilterConfig
    pnp: PnPConfig


@dataclass(slots=True)
class OutputConfig:
    """终端、窗口和日志输出配置。"""

    print_json_lines: bool
    show_window: bool
    save_csv: Path | None


@dataclass(slots=True)
class ProjectConfig:
    """项目完整配置对象。"""

    root_dir: Path
    camera: CameraConfig
    mocap: MocapConfig
    object_model: ObjectModelConfig
    yolo6d: YOLO6DConfig
    output: OutputConfig


def _resolve_path(root_dir: Path, raw_path: str | None, local_paths: LocalPaths | None = None) -> Path | None:
    """把 YAML 中的相对路径解析成绝对路径。"""
    return resolve_path(raw_path, project_root=root_dir, local_paths=local_paths)


def _load_pose(raw_pose: dict, parent_frame: str, child_frame: str) -> PoseSE3:
    """从字典形式的 pose 配置构造 PoseSE3。"""
    return pose_from_quaternion_translation(
        parent_frame=parent_frame,
        child_frame=child_frame,
        translation_m=np.asarray(raw_pose["translation_m"], dtype=np.float64),
        quaternion_xyzw=np.asarray(raw_pose["quaternion_xyzw"], dtype=np.float64),
    )


def _load_optional_pose(raw_pose: dict | None, parent_frame: str, child_frame: str) -> PoseSE3 | None:
    """允许为空的 pose 读取包装。"""
    if raw_pose is None:
        return None
    return _load_pose(raw_pose, parent_frame=parent_frame, child_frame=child_frame)


def load_config(config_path: str | Path, paths_config: str | Path | None = None) -> ProjectConfig:
    """从 YAML 加载并组装项目配置。"""
    config_file = Path(config_path).resolve()
    with config_file.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    # 配置文件默认放在 configs/ 下，所以 parents[1] 是项目根目录。
    root_dir = config_file.parents[1]
    local_paths = load_local_paths(paths_config) if paths_config is not None else None

    camera = CameraConfig(**raw["camera"])

    mocap_raw = raw["mocap"]
    # 空字符串和 null 都表示“不使用相机刚体”，例如固定相机静态外参模式。
    camera_rigid_body_raw = mocap_raw.get("camera_rigid_body")
    camera_rigid_body = None if camera_rigid_body_raw in {None, ""} else str(camera_rigid_body_raw)
    object_rigid_body = str(mocap_raw["object_rigid_body"])
    camera_optical_frame = str(mocap_raw.get("camera_optical_frame", "camera_optical"))
    object_model_frame = str(mocap_raw.get("object_model_frame", "object_model"))

    camera_rigid_to_optical = None
    if camera_rigid_body is not None:
        # 只有声明了相机刚体时，T_camera_rigid_to_optical 才有意义。
        camera_rigid_to_optical = _load_optional_pose(
            mocap_raw.get("T_camera_rigid_to_optical"),
            parent_frame=camera_rigid_body,
            child_frame=camera_optical_frame,
        )

    world_camera_optical = _load_optional_pose(
        # 固定相机可直接配置 T_world_camera_optical；动态相机则保持 null。
        mocap_raw.get("T_world_camera_optical"),
        parent_frame="mocap_world",
        child_frame=camera_optical_frame,
    )

    mocap = MocapConfig(
        enabled=bool(mocap_raw["enabled"]),
        mode=str(mocap_raw["mode"]),
        csv_path=_resolve_path(root_dir, mocap_raw.get("csv_path"), local_paths),
        camera_rigid_body=camera_rigid_body,
        object_rigid_body=object_rigid_body,
        max_time_diff_s=float(mocap_raw["max_time_diff_s"]),
        time_offset_s=float(mocap_raw.get("time_offset_s", 0.0)),
        camera_optical_frame=camera_optical_frame,
        object_model_frame=object_model_frame,
        camera_rigid_to_optical=camera_rigid_to_optical,
        world_camera_optical=world_camera_optical,
        object_rigid_to_model=_load_pose(
            mocap_raw["T_object_rigid_to_model"],
            parent_frame=object_rigid_body,
            child_frame=object_model_frame,
        ),
    )

    object_model_raw = raw["object_model"]
    dimensions_raw = object_model_raw.get("dimensions_m")
    extents_raw = object_model_raw.get("extents_m")
    model_json_raw = object_model_raw.get("model_json_path")
    object_model = ObjectModelConfig(
        label=str(object_model_raw["label"]),
        keypoints_mode=str(object_model_raw["keypoints_mode"]),
        dimensions_m=None if dimensions_raw is None else tuple(float(v) for v in dimensions_raw),
        extents_m=None if extents_raw is None else tuple(float(v) for v in extents_raw),
        model_json_path=_resolve_path(root_dir, model_json_raw, local_paths),
        include_center=bool(object_model_raw.get("include_center", True)),
    )

    yolo_raw = raw["yolo6d"]
    pnp_raw = yolo_raw["pnp"]
    # PnP 参数单独成组，便于离线和实时共用同一套求解配置。
    pnp = PnPConfig(
        ransac_reproj_threshold_px=float(pnp_raw["ransac_reproj_threshold_px"]),
        iterations_count=int(pnp_raw["iterations_count"]),
        confidence=float(pnp_raw["confidence"]),
        min_keypoint_score=float(pnp_raw["min_keypoint_score"]),
    )

    roi_raw = yolo_raw.get("roi_tracker", {})
    # 旧配置可能没有 roi_tracker 字段，因此这里提供保守默认值。
    roi_tracker = ROITrackerConfig(
        enabled=bool(roi_raw.get("enabled", False)),
        expand_ratio=float(roi_raw.get("expand_ratio", 2.2)),
        min_size_px=int(roi_raw.get("min_size_px", 180)),
        full_frame_interval=int(roi_raw.get("full_frame_interval", 8)),
        max_missed_frames=int(roi_raw.get("max_missed_frames", 3)),
        square_crop=bool(roi_raw.get("square_crop", True)),
        predict_motion=bool(roi_raw.get("predict_motion", False)),
        velocity_alpha=float(roi_raw.get("velocity_alpha", 0.65)),
        max_prediction_frames=int(roi_raw.get("max_prediction_frames", 4)),
    )

    temporal_raw = yolo_raw.get("temporal_filter", {})
    # 时间滤波也是可选项；缺字段时默认关闭。
    temporal_filter = TemporalFilterConfig(
        enabled=bool(temporal_raw.get("enabled", False)),
        translation_alpha=float(temporal_raw.get("translation_alpha", 0.45)),
        rotation_alpha=float(temporal_raw.get("rotation_alpha", 0.35)),
        max_translation_jump_m=float(temporal_raw.get("max_translation_jump_m", 0.35)),
        max_angle_jump_deg=float(temporal_raw.get("max_angle_jump_deg", 30.0)),
        hold_last_frames=int(temporal_raw.get("hold_last_frames", 2)),
    )

    yolo6d = YOLO6DConfig(
        backend=str(yolo_raw["backend"]),
        conf_threshold=float(yolo_raw["conf_threshold"]),
        replay_json_path=_resolve_path(root_dir, yolo_raw.get("replay_json_path"), local_paths),
        model_path=_resolve_path(root_dir, yolo_raw.get("model_path"), local_paths),
        inference_imgsz=int(yolo_raw.get("inference_imgsz", 640)),
        inference_device=str(yolo_raw.get("inference_device", "")),
        replay_timestamp_tolerance_s=float(yolo_raw.get("replay_timestamp_tolerance_s", 0.05)),
        roi_tracker=roi_tracker,
        temporal_filter=temporal_filter,
        pnp=pnp,
    )

    output_raw = raw["output"]
    output = OutputConfig(
        print_json_lines=bool(output_raw.get("print_json_lines", True)),
        show_window=bool(output_raw.get("show_window", False)),
        save_csv=_resolve_path(root_dir, output_raw.get("save_csv"), local_paths),
    )

    return ProjectConfig(
        root_dir=root_dir,
        camera=camera,
        mocap=mocap,
        object_model=object_model,
        yolo6d=yolo6d,
        output=output,
    )
