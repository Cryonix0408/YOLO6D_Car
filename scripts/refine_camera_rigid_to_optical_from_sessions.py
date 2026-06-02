"""基于多 session 结果细化相机刚体外参。"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import yaml
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
# 支持直接运行脚本，不依赖 editable install。
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.config import ProjectConfig, load_config
from yolo6d_car.mocap.csv_provider import CSVRigidBodyProvider
from yolo6d_car.object_model import build_object_keypoints
from yolo6d_car.pose.pnp import project_points
from yolo6d_car.transforms import matrix_to_quaternion, pose_from_matrix
from yolo6d_car.types import CameraIntrinsics, PoseSE3


@dataclass(slots=True)
class SessionSpec:
    """一组图像采集目录及其对应的 Mocap CSV。"""

    samples_dir: Path
    csv_path: Path


@dataclass(slots=True)
class Observation:
    """优化使用的一帧观测：Mocap 位姿 + YOLO 2D 关键点 + 相机内参。"""

    session_name: str
    image_path: Path
    timestamp_s: float
    intrinsics: CameraIntrinsics
    world_camera_rigid: PoseSE3
    world_object_rigid: PoseSE3
    image_points_px: np.ndarray
    keypoint_weights: np.ndarray
    detection_confidence: float


def parse_args() -> argparse.Namespace:
    """定义多 session 外参细化参数。"""
    parser = argparse.ArgumentParser(
        description="Use existing object sessions to refine mocap.T_camera_rigid_to_optical by minimizing 2D keypoint reprojection error."
    )
    parser.add_argument("--config", required=True, help="Base project YAML config.")
    parser.add_argument("--model", required=True, help="Trained Ultralytics pose model path (.pt).")
    parser.add_argument(
        "--samples-dir",
        action="append",
        required=True,
        help="Session directory containing images/, samples.csv and intrinsics.json. Repeat for multiple sessions.",
    )
    parser.add_argument(
        "--csv-path",
        action="append",
        required=True,
        help="Mocap CSV path matching each --samples-dir. Repeat in the same order.",
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / "outputs" / "calibration" / "camera_rigid_to_optical_refined_from_sessions.json"),
        help="JSON output path.",
    )
    parser.add_argument(
        "--config-out",
        default=None,
        help="Optional YAML path. If set, write a copy of --config with refined mocap.T_camera_rigid_to_optical.",
    )
    parser.add_argument("--imgsz", type=int, default=640, help="Ultralytics inference image size.")
    parser.add_argument("--device", default="", help="Ultralytics inference device, for example 0 or cpu.")
    parser.add_argument("--conf-threshold", type=float, default=0.25, help="Detection confidence threshold.")
    parser.add_argument("--min-keypoint-score", type=float, default=0.2, help="Minimum keypoint confidence used in optimization.")
    parser.add_argument("--max-samples-per-session", type=int, default=150, help="Max frames to use per session.")
    parser.add_argument("--translation-prior-sigma-m", type=float, default=0.04, help="Small-delta translation prior sigma.")
    parser.add_argument("--rotation-prior-sigma-deg", type=float, default=8.0, help="Small-delta rotation prior sigma in degrees.")
    parser.add_argument("--time-offset-s", type=float, default=None, help="Optional per-run mocap time offset override.")
    return parser.parse_args()


def _load_intrinsics(path: Path) -> CameraIntrinsics:
    """读取采集 session 保存的相机内参。"""
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
    """解析 FzMotion StartTime 元数据。"""
    text = (text or "").strip()
    if not text:
        return None
    for fmt in ("%Y.%m.%d %H:%M:%S:%f", "%Y.%m.%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None


def _load_mocap_start_time(mocap_csv_path: Path) -> datetime | None:
    """读取 FzMotion CSV 第一行的 StartTime。"""
    with mocap_csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        first_row = next(reader, None)
    if not first_row:
        return None

    stripped = [cell.strip() for cell in first_row]
    for idx in range(0, len(stripped) - 1, 2):
        key = stripped[idx]
        value = stripped[idx + 1]
        if key == "StartTime":
            return _parse_fzmotion_start_time(value)
    return None


def _resolve_sample_timestamp_s(row: dict[str, str], mocap_start_dt: datetime | None) -> tuple[float, str]:
    """把 samples.csv 时间字段转换为 Mocap 相对秒。"""
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


def _read_samples(samples_dir: Path) -> list[dict[str, str]]:
    """读取一个 session 的 samples.csv。"""
    samples_csv = samples_dir / "samples.csv"
    if not samples_csv.exists():
        raise FileNotFoundError(f"Missing samples.csv in {samples_dir}")
    with samples_csv.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _sample_rows(rows: list[dict[str, str]], max_samples: int) -> list[dict[str, str]]:
    """从 session 中均匀抽样，控制优化规模和运行时间。"""
    if max_samples <= 0 or len(rows) <= max_samples:
        return rows
    indexes = np.linspace(0, len(rows) - 1, num=max_samples, dtype=int)
    return [rows[int(idx)] for idx in indexes]


def _load_model(model_path: Path):
    """延迟加载 Ultralytics 模型，便于缺依赖时给出明确错误。"""
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("Ultralytics is required. Install it with: python -m pip install ultralytics") from exc
    return YOLO(str(model_path))


def _best_detection(result, label: str, conf_threshold: float):
    """从 Ultralytics 结果中取置信度最高的一辆车检测。"""
    boxes = getattr(result, "boxes", None)
    keypoints = getattr(result, "keypoints", None)
    if boxes is None or keypoints is None or len(boxes) == 0:
        return None

    image_points = keypoints.xy.cpu().numpy()
    keypoint_scores = None
    if getattr(keypoints, "conf", None) is not None:
        keypoint_scores = keypoints.conf.cpu().numpy()
    boxes_conf = boxes.conf.cpu().numpy() if getattr(boxes, "conf", None) is not None else None

    best = None
    best_conf = -math.inf
    count = min(len(image_points), len(boxes))
    for idx in range(count):
        confidence = 1.0 if boxes_conf is None else float(boxes_conf[idx])
        if confidence < conf_threshold:
            continue
        if confidence > best_conf:
            best_conf = confidence
            best = {
                "label": label,
                "confidence": confidence,
                "image_points_px": np.asarray(image_points[idx], dtype=np.float64),
                "keypoint_scores": None if keypoint_scores is None else np.asarray(keypoint_scores[idx], dtype=np.float64),
            }
    return best


def _object_model_config_dict(config: ProjectConfig) -> dict:
    """把强类型 object_model 配置转换成 build_object_keypoints 需要的 dict。"""
    mode = config.object_model.keypoints_mode.lower()
    payload = {
        "keypoints_mode": config.object_model.keypoints_mode,
        "include_center": config.object_model.include_center,
    }
    if mode == "custom" and config.object_model.model_json_path is not None:
        payload["model_json_path"] = str(config.object_model.model_json_path)
    elif mode in {"extents_cuboid", "asymmetric_cuboid"} and config.object_model.extents_m is not None:
        payload["extents_m"] = config.object_model.extents_m
    else:
        payload["dimensions_m"] = config.object_model.dimensions_m
    return payload


def _build_observations(
    config: ProjectConfig,
    sessions: list[SessionSpec],
    model_path: Path,
    imgsz: int,
    device: str,
    conf_threshold: float,
    min_keypoint_score: float,
    max_samples_per_session: int,
    time_offset_override: float | None,
) -> tuple[list[Observation], np.ndarray]:
    """跑 YOLO 检测并收集可用于外参优化的多 session 观测。"""
    model = _load_model(model_path)
    object_points_xyz = build_object_keypoints(_object_model_config_dict(config))
    observations: list[Observation] = []

    mocap_time_offset_s = config.mocap.time_offset_s if time_offset_override is None else float(time_offset_override)

    for session in sessions:
        # 每个 session 有独立内参、图像清单和 Mocap CSV。
        intrinsics = _load_intrinsics(session.samples_dir / "intrinsics.json")
        provider = CSVRigidBodyProvider(session.csv_path)
        mocap_start_dt = _load_mocap_start_time(session.csv_path)
        rows = _sample_rows(_read_samples(session.samples_dir), max_samples_per_session)

        used_count = 0
        for row in rows:
            timestamp_s, _ = _resolve_sample_timestamp_s(row, mocap_start_dt)
            mocap_timestamp_s = timestamp_s + mocap_time_offset_s

            world_camera_rigid = provider.get_pose(
                rigid_body=str(config.mocap.camera_rigid_body),
                timestamp_s=mocap_timestamp_s,
                max_time_diff_s=float(config.mocap.max_time_diff_s),
            )
            world_object_rigid = provider.get_pose(
                rigid_body=str(config.mocap.object_rigid_body),
                timestamp_s=mocap_timestamp_s,
                max_time_diff_s=float(config.mocap.max_time_diff_s),
            )
            if world_camera_rigid is None or world_object_rigid is None:
                continue

            raw_image_path = Path(row["image_path"])
            image_path = raw_image_path if raw_image_path.is_absolute() else (session.samples_dir / raw_image_path)
            if not image_path.exists():
                continue

            results = model.predict(
                source=str(image_path),
                imgsz=imgsz,
                device=device,
                conf=conf_threshold,
                verbose=False,
            )
            detection = _best_detection(results[0], config.object_model.label, conf_threshold)
            if detection is None:
                continue

            # keypoint score 作为重投影残差权重，低分点影响更小。
            keypoint_scores = detection["keypoint_scores"]
            if keypoint_scores is None:
                weights = np.ones((detection["image_points_px"].shape[0],), dtype=np.float64)
            else:
                weights = np.asarray(keypoint_scores, dtype=np.float64).reshape(-1)

            valid_mask = np.isfinite(detection["image_points_px"]).all(axis=1) & (weights >= min_keypoint_score)
            if np.count_nonzero(valid_mask) < 4:
                continue

            observations.append(
                Observation(
                    session_name=session.samples_dir.name,
                    image_path=image_path,
                    timestamp_s=timestamp_s,
                    intrinsics=intrinsics,
                    world_camera_rigid=world_camera_rigid,
                    world_object_rigid=world_object_rigid,
                    image_points_px=np.asarray(detection["image_points_px"], dtype=np.float64),
                    keypoint_weights=weights,
                    detection_confidence=float(detection["confidence"]),
                )
            )
            used_count += 1

        print(json.dumps({
            "session": session.samples_dir.name,
            "csv_path": str(session.csv_path),
            "sample_rows_considered": len(rows),
            "observations_built": used_count,
        }, ensure_ascii=False))

    if not observations:
        raise RuntimeError("No valid observations were built for extrinsic refinement.")

    return observations, object_points_xyz


def _candidate_pose(base_matrix: np.ndarray, delta_params: np.ndarray) -> np.ndarray:
    """把 6 维小量左乘到基础外参上，得到候选外参。"""
    delta_rot = Rotation.from_rotvec(delta_params[:3]).as_matrix()
    delta_t = np.asarray(delta_params[3:6], dtype=np.float64)

    delta_T = np.eye(4, dtype=np.float64)
    delta_T[:3, :3] = delta_rot
    delta_T[:3, 3] = delta_t
    return delta_T @ base_matrix


def _compute_pose_camera_object(
    world_camera_rigid: PoseSE3,
    world_object_rigid: PoseSE3,
    candidate_camera_rigid_to_optical: np.ndarray,
    object_rigid_to_model: PoseSE3,
) -> PoseSE3:
    """根据候选外参计算 T_camera_optical_object_model。"""
    world_camera_optical = world_camera_rigid.as_matrix() @ candidate_camera_rigid_to_optical
    world_object_model = world_object_rigid.as_matrix() @ object_rigid_to_model.as_matrix()
    camera_object_model = np.linalg.inv(world_camera_optical) @ world_object_model
    return pose_from_matrix(
        parent_frame="camera_optical",
        child_frame=object_rigid_to_model.child_frame,
        matrix=camera_object_model,
        timestamp_s=world_object_rigid.timestamp_s,
    )


def _residuals(
    delta_params: np.ndarray,
    base_camera_rigid_to_optical: np.ndarray,
    observations: list[Observation],
    object_points_xyz: np.ndarray,
    object_rigid_to_model: PoseSE3,
    translation_prior_sigma_m: float,
    rotation_prior_sigma_rad: float,
) -> np.ndarray:
    """优化残差：预测投影点与 YOLO 关键点的像素误差，加上小量先验。"""
    candidate = _candidate_pose(base_camera_rigid_to_optical, delta_params)
    residuals: list[float] = []

    for obs in observations:
        pose_camera_object = _compute_pose_camera_object(
            obs.world_camera_rigid,
            obs.world_object_rigid,
            candidate,
            object_rigid_to_model,
        )
        projected = project_points(object_points_xyz, pose_camera_object, obs.intrinsics)
        valid_mask = np.isfinite(obs.image_points_px).all(axis=1) & np.isfinite(projected).all(axis=1) & (obs.keypoint_weights > 0.0)
        if np.count_nonzero(valid_mask) < 4:
            continue

        deltas = projected[valid_mask] - obs.image_points_px[valid_mask]
        # 用关键点置信度开方做权重，避免高分点过度支配优化。
        weights = np.sqrt(np.clip(obs.keypoint_weights[valid_mask], 1e-3, 1.0))
        weighted = deltas * weights[:, None]
        residuals.extend(weighted.reshape(-1).tolist())

    residuals.extend((delta_params[3:6] / translation_prior_sigma_m).tolist())
    residuals.extend((delta_params[0:3] / rotation_prior_sigma_rad).tolist())
    return np.asarray(residuals, dtype=np.float64)


def _mean_reprojection_error_px(
    candidate_camera_rigid_to_optical: np.ndarray,
    observations: list[Observation],
    object_points_xyz: np.ndarray,
    object_rigid_to_model: PoseSE3,
) -> float:
    """计算一组观测在某个外参下的平均帧级 RMS 重投影误差。"""
    frame_errors = []
    for obs in observations:
        pose_camera_object = _compute_pose_camera_object(
            obs.world_camera_rigid,
            obs.world_object_rigid,
            candidate_camera_rigid_to_optical,
            object_rigid_to_model,
        )
        projected = project_points(object_points_xyz, pose_camera_object, obs.intrinsics)
        valid_mask = np.isfinite(obs.image_points_px).all(axis=1) & np.isfinite(projected).all(axis=1) & (obs.keypoint_weights > 0.0)
        if np.count_nonzero(valid_mask) < 4:
            continue
        deltas = projected[valid_mask] - obs.image_points_px[valid_mask]
        frame_errors.append(float(np.sqrt(np.mean(np.sum(deltas * deltas, axis=1)))))
    if not frame_errors:
        return float("nan")
    return float(np.mean(frame_errors))


def _transform_to_dict(matrix: np.ndarray) -> dict[str, object]:
    """把 4x4 变换转换成 JSON 友好的结构。"""
    matrix = np.asarray(matrix, dtype=np.float64).reshape(4, 4)
    return {
        "translation_m": matrix[:3, 3].tolist(),
        "quaternion_xyzw": matrix_to_quaternion(matrix[:3, :3]).tolist(),
        "matrix": matrix.tolist(),
    }


def _write_config_with_refined_extrinsic(config_path: Path, out_path: Path, refined_transform: np.ndarray) -> None:
    """把细化后的相机外参写回一份新的 YAML 配置。"""
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    raw["mocap"]["T_camera_rigid_to_optical"] = {
        "translation_m": refined_transform[:3, 3].tolist(),
        "quaternion_xyzw": matrix_to_quaternion(refined_transform[:3, :3]).tolist(),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")


def main() -> None:
    """从多 session 构建观测，优化相机刚体外参并保存报告。"""
    args = parse_args()
    if len(args.samples_dir) != len(args.csv_path):
        raise SystemExit("--samples-dir and --csv-path must have the same count.")

    config_path = Path(args.config).resolve()
    model_path = Path(args.model).resolve()
    out_path = Path(args.out).resolve()
    config = load_config(config_path)

    if config.mocap.camera_rigid_to_optical is None:
        raise RuntimeError("Config does not contain mocap.T_camera_rigid_to_optical")
    if config.mocap.camera_rigid_body is None:
        raise RuntimeError("Config does not contain mocap.camera_rigid_body")

    sessions = [
        SessionSpec(samples_dir=Path(samples_dir).resolve(), csv_path=Path(csv_path).resolve())
        for samples_dir, csv_path in zip(args.samples_dir, args.csv_path)
    ]

    observations, object_points_xyz = _build_observations(
        config=config,
        sessions=sessions,
        model_path=model_path,
        imgsz=int(args.imgsz),
        device=str(args.device),
        conf_threshold=float(args.conf_threshold),
        min_keypoint_score=float(args.min_keypoint_score),
        max_samples_per_session=int(args.max_samples_per_session),
        time_offset_override=args.time_offset_s,
    )

    base_matrix = config.mocap.camera_rigid_to_optical.as_matrix()
    before_error_px = _mean_reprojection_error_px(
        candidate_camera_rigid_to_optical=base_matrix,
        observations=observations,
        object_points_xyz=object_points_xyz,
        object_rigid_to_model=config.mocap.object_rigid_to_model,
    )

    rotation_prior_sigma_rad = math.radians(float(args.rotation_prior_sigma_deg))
    # 只优化相对当前外参的 6 维小量，配合先验保持细化幅度可控。
    result = least_squares(
        fun=_residuals,
        x0=np.zeros((6,), dtype=np.float64),
        args=(
            base_matrix,
            observations,
            object_points_xyz,
            config.mocap.object_rigid_to_model,
            float(args.translation_prior_sigma_m),
            rotation_prior_sigma_rad,
        ),
        loss="soft_l1",
        f_scale=4.0,
        max_nfev=80,
        verbose=0,
    )

    refined_matrix = _candidate_pose(base_matrix, result.x)
    after_error_px = _mean_reprojection_error_px(
        candidate_camera_rigid_to_optical=refined_matrix,
        observations=observations,
        object_points_xyz=object_points_xyz,
        object_rigid_to_model=config.mocap.object_rigid_to_model,
    )

    payload = {
        "config": str(config_path),
        "model": str(model_path),
        "sessions": [
            {
                "samples_dir": str(spec.samples_dir),
                "csv_path": str(spec.csv_path),
            }
            for spec in sessions
        ],
        "num_observations": len(observations),
        "optimization_success": bool(result.success),
        "optimization_message": result.message,
        "before_mean_reprojection_error_px": before_error_px,
        "after_mean_reprojection_error_px": after_error_px,
        "delta_rotvec_rad": result.x[:3].tolist(),
        "delta_rotvec_deg": np.degrees(result.x[:3]).tolist(),
        "delta_translation_m": result.x[3:6].tolist(),
        "base_T_camera_rigid_to_optical": _transform_to_dict(base_matrix),
        "refined_T_camera_rigid_to_optical": _transform_to_dict(refined_matrix),
        "metadata": {
            "translation_prior_sigma_m": float(args.translation_prior_sigma_m),
            "rotation_prior_sigma_deg": float(args.rotation_prior_sigma_deg),
            "imgsz": int(args.imgsz),
            "conf_threshold": float(args.conf_threshold),
            "min_keypoint_score": float(args.min_keypoint_score),
            "max_samples_per_session": int(args.max_samples_per_session),
            "time_offset_s": config.mocap.time_offset_s if args.time_offset_s is None else float(args.time_offset_s),
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.config_out:
        config_out = Path(args.config_out).resolve()
        _write_config_with_refined_extrinsic(config_path, config_out, refined_matrix)
        print(json.dumps({"config_out": str(config_out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

