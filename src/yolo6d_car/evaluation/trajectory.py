"""本文件作用：
    读取 replay 输出 CSV，并提取 raw / filtered pose 轨迹。

在 YOLO6D_Car pipeline 中的位置：
    evaluation 的数据加载层。它只负责把 CSV 变成 NumPy 数组，不计算指标。

主要输入：
    pose_results.csv。优先读取 raw_tx/raw_ty/... 和 filtered_tx/filtered_ty/... 字段。

主要输出：
    PoseCsvData，包含 timestamps、raw_pose、filtered_pose、tracking_states 等。

注意事项：
    如果没有 timestamp，会根据 frame_id/default_fps 生成时间戳；
    如果没有 filtered pose，会返回 None，并让上层给出清楚 warning。
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


RAW_COLUMNS = ("raw_tx", "raw_ty", "raw_tz", "raw_rx", "raw_ry", "raw_rz")
FILTERED_COLUMNS = ("filtered_tx", "filtered_ty", "filtered_tz", "filtered_rx", "filtered_ry", "filtered_rz")
PREDICTION_TRANSLATION_COLUMNS = ("prediction_tx", "prediction_ty", "prediction_tz")
PREDICTION_QUATERNION_COLUMNS = ("prediction_qx", "prediction_qy", "prediction_qz", "prediction_qw")


@dataclass(frozen=True, slots=True)
class PoseCsvData:
    """Parsed pose CSV contents."""

    rows: list[dict[str, str]]
    headers: list[str]
    timestamps: np.ndarray
    raw_pose: np.ndarray
    filtered_pose: np.ndarray | None
    tracking_states: list[str]
    valid_measurements: list[bool]
    warnings: list[str]


def _float_or_nan(value: str | None) -> float:
    """Parse a float with NaN for empty or invalid cells."""
    if value is None or str(value).strip() == "":
        return float("nan")
    try:
        return float(value)
    except ValueError:
        return float("nan")


def load_pose_csv(csv_path: str | Path, *, default_fps: float = 30.0) -> PoseCsvData:
    """加载 replay pose CSV 并返回 raw/filtered 轨迹。

    参数：
        csv_path: replay 输出 CSV。
        default_fps: timestamp 缺失时的 fallback 帧率。

    返回：
        PoseCsvData。raw_pose shape=(N, 6)，filtered_pose 可能为 None。
    """
    path = Path(csv_path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        headers = list(reader.fieldnames or [])
    if not rows:
        raise RuntimeError(f"Pose CSV has no data rows: {path}")

    warnings = handle_missing_columns(headers)
    timestamps, timestamp_warnings = handle_timestamps(rows, default_fps=default_fps)
    warnings.extend(timestamp_warnings)
    raw_pose = extract_raw_pose(rows, headers)
    filtered_pose = extract_filtered_pose(rows, headers)
    states = [row.get("tracking_state", "") for row in rows]
    valid = [_parse_bool(row.get("kalman_valid_measurement", "")) for row in rows]
    return PoseCsvData(
        rows=rows,
        headers=headers,
        timestamps=timestamps,
        raw_pose=raw_pose,
        filtered_pose=filtered_pose,
        tracking_states=states,
        valid_measurements=valid,
        warnings=warnings,
    )


def extract_raw_pose(rows: list[dict[str, str]], headers: list[str]) -> np.ndarray:
    """Extract raw [tx, ty, tz, rx, ry, rz] pose array."""
    missing = [col for col in RAW_COLUMNS if col not in headers]
    if not missing:
        return np.array([[_float_or_nan(row.get(col)) for col in RAW_COLUMNS] for row in rows], dtype=np.float64)

    prediction_missing = [
        col for col in (*PREDICTION_TRANSLATION_COLUMNS, *PREDICTION_QUATERNION_COLUMNS) if col not in headers
    ]
    if prediction_missing:
        raise RuntimeError(f"raw pose columns not found: {missing}; prediction pose fallback missing: {prediction_missing}")

    pose_rows: list[list[float]] = []
    for row in rows:
        translation = [_float_or_nan(row.get(col)) for col in PREDICTION_TRANSLATION_COLUMNS]
        quaternion = np.array([_float_or_nan(row.get(col)) for col in PREDICTION_QUATERNION_COLUMNS], dtype=np.float64)
        rvec = _quaternion_xyzw_to_rvec(quaternion)
        pose_rows.append([*translation, *rvec.tolist()])
    return np.array(pose_rows, dtype=np.float64)


def extract_filtered_pose(rows: list[dict[str, str]], headers: list[str]) -> np.ndarray | None:
    """Extract filtered [tx, ty, tz, rx, ry, rz] pose array if present."""
    missing = [col for col in FILTERED_COLUMNS if col not in headers]
    if missing:
        return None
    return np.array([[_float_or_nan(row.get(col)) for col in FILTERED_COLUMNS] for row in rows], dtype=np.float64)


def handle_missing_columns(headers: list[str]) -> list[str]:
    """Return warnings for optional missing columns and clear errors for required ones."""
    warnings: list[str] = []
    raw_missing = [col for col in RAW_COLUMNS if col not in headers]
    if raw_missing:
        prediction_missing = [
            col for col in (*PREDICTION_TRANSLATION_COLUMNS, *PREDICTION_QUATERNION_COLUMNS) if col not in headers
        ]
        if prediction_missing:
            warnings.append(f"raw pose columns missing: {raw_missing}")
        else:
            warnings.append("raw pose columns missing; using prediction translation/quaternion as raw pose fallback.")
    filtered_missing = [col for col in FILTERED_COLUMNS if col not in headers]
    if filtered_missing:
        warnings.append("filtered pose columns not found; run replay with --kalman-config first.")
    if "tracking_state" not in headers:
        warnings.append("tracking_state column missing; state counts will be empty.")
    if "kalman_valid_measurement" not in headers:
        warnings.append("kalman_valid_measurement column missing; valid/invalid counts will be zero.")
    return warnings


def handle_timestamps(rows: list[dict[str, str]], default_fps: float = 30.0) -> tuple[np.ndarray, list[str]]:
    """Load timestamps, falling back to frame_id/frame_index and default_fps."""
    warnings: list[str] = []
    if "timestamp_s" in rows[0]:
        timestamps = np.array([_float_or_nan(row.get("timestamp_s")) for row in rows], dtype=np.float64)
    elif "timestamp" in rows[0]:
        timestamps = np.array([_float_or_nan(row.get("timestamp")) for row in rows], dtype=np.float64)
    else:
        frame_key = "frame_id" if "frame_id" in rows[0] else "frame_index" if "frame_index" in rows[0] else None
        if frame_key is None:
            frames = np.arange(len(rows), dtype=np.float64)
        else:
            frames = np.array([_float_or_nan(row.get(frame_key)) for row in rows], dtype=np.float64)
            if not np.isfinite(frames).all():
                frames = np.arange(len(rows), dtype=np.float64)
        timestamps = frames / max(float(default_fps), 1e-6)
        warnings.append("timestamp column missing; generated timestamps from frame_id/frame_index and default_fps.")

    if not np.isfinite(timestamps).all():
        timestamps = np.arange(len(rows), dtype=np.float64) / max(float(default_fps), 1e-6)
        warnings.append("timestamp values invalid; generated timestamps from row index and default_fps.")
    return timestamps, warnings


def _parse_bool(value: str) -> bool:
    """Parse common truthy CSV strings."""
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _quaternion_xyzw_to_rvec(quaternion_xyzw: np.ndarray) -> np.ndarray:
    """Convert an xyzw quaternion to a Rodrigues rotation vector."""
    if not np.isfinite(quaternion_xyzw).all():
        return np.full(3, np.nan, dtype=np.float64)

    q = np.asarray(quaternion_xyzw, dtype=np.float64).reshape(4)
    norm = np.linalg.norm(q)
    if norm <= 1e-12:
        return np.full(3, np.nan, dtype=np.float64)
    x, y, z, w = q / norm
    rotation = np.array(
        [
            [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)],
            [2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)],
            [2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )
    try:
        import cv2

        rvec, _ = cv2.Rodrigues(rotation)
        return rvec.reshape(3)
    except Exception:
        angle = float(2.0 * np.arccos(np.clip(w, -1.0, 1.0)))
        sin_half = np.sqrt(max(1.0 - w * w, 0.0))
        if sin_half < 1e-12:
            return np.zeros(3, dtype=np.float64)
        axis = np.array([x, y, z], dtype=np.float64) / sin_half
        return axis * angle
