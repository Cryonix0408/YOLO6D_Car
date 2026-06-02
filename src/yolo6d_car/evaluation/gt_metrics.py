"""本文件作用：
    计算 replay 预测 pose 与预处理 Mocap GT pose 的误差。

在 YOLO6D_Car pipeline 中的位置：
    evaluation 层。evaluate_pose_results.py 在传入 --gt-csv 时调用这里。

主要输入：
    gt_pose.csv，字段必须是 timestamp, gt_tx, gt_ty, gt_tz, gt_rx, gt_ry, gt_rz。

主要输出：
    translation RMSE、ATE、rotation error、RPE、per-axis error 和 error-over-time 序列。

注意事项：
    第一版不直接解析 FzMotion 原始 CSV；需要先转换成 gt_pose.csv。
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


GT_COLUMNS = ("timestamp", "gt_tx", "gt_ty", "gt_tz", "gt_rx", "gt_ry", "gt_rz")


@dataclass(frozen=True, slots=True)
class GtPoseData:
    """Preprocessed GT pose trajectory."""

    rows: list[dict[str, str]]
    headers: list[str]
    timestamps: np.ndarray
    pose: np.ndarray


@dataclass(frozen=True, slots=True)
class AlignedGtData:
    """Prediction poses aligned to nearest GT timestamps."""

    prediction_indices: np.ndarray
    gt_indices: np.ndarray
    prediction_timestamps: np.ndarray
    gt_timestamps: np.ndarray
    time_diffs_s: np.ndarray
    gt_pose: np.ndarray


def load_gt_pose_csv(csv_path: str | Path) -> GtPoseData:
    """读取预处理后的 GT pose CSV。

    Required columns:
    timestamp, gt_tx, gt_ty, gt_tz, gt_rx, gt_ry, gt_rz

    如果传入原始 FzMotion CSV，这里会明确报错并提示先转换。
    """
    path = Path(csv_path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        headers = list(reader.fieldnames or [])
    if not rows:
        raise RuntimeError(f"GT CSV has no data rows: {path}")
    missing = [column for column in GT_COLUMNS if column not in headers]
    if missing:
        preview = ", ".join(headers[:20])
        raise RuntimeError(
            "Unsupported GT CSV format. First version only supports preprocessed gt_pose.csv "
            f"with columns {GT_COLUMNS}. Missing {missing}. "
            f"If this is a raw FzMotion CSV, convert it to gt_pose.csv first. Headers: {preview}"
        )
    timestamps = np.asarray([_float_or_nan(row.get("timestamp")) for row in rows], dtype=np.float64)
    pose = np.asarray(
        [[_float_or_nan(row.get(column)) for column in GT_COLUMNS[1:]] for row in rows],
        dtype=np.float64,
    )
    finite = np.isfinite(timestamps) & np.isfinite(pose).all(axis=1)
    if not np.any(finite):
        raise RuntimeError(f"GT CSV has no finite timestamp/pose rows: {path}")
    timestamps = timestamps[finite]
    pose = pose[finite]
    order = np.argsort(timestamps)
    return GtPoseData(rows=rows, headers=headers, timestamps=timestamps[order], pose=pose[order])


def align_gt_to_predictions(
    prediction_timestamps: np.ndarray,
    gt_data: GtPoseData,
    *,
    max_time_diff_s: float = 0.03,
) -> AlignedGtData:
    """Nearest-neighbor align GT poses to prediction timestamps."""
    pred_ts = np.asarray(prediction_timestamps, dtype=np.float64).reshape(-1)
    gt_ts = np.asarray(gt_data.timestamps, dtype=np.float64).reshape(-1)
    if pred_ts.size == 0 or gt_ts.size == 0:
        empty_int = np.empty(0, dtype=np.int64)
        empty_float = np.empty(0, dtype=np.float64)
        return AlignedGtData(empty_int, empty_int, empty_float, empty_float, empty_float, np.empty((0, 6), dtype=np.float64))

    nearest = np.searchsorted(gt_ts, pred_ts)
    chosen: list[int] = []
    pred_indices: list[int] = []
    diffs: list[float] = []
    for pred_index, insert_index in enumerate(nearest):
        candidates = []
        if insert_index < gt_ts.size:
            candidates.append(int(insert_index))
        if insert_index > 0:
            candidates.append(int(insert_index - 1))
        if not candidates:
            continue
        best = min(candidates, key=lambda idx: abs(float(gt_ts[idx] - pred_ts[pred_index])))
        diff = abs(float(gt_ts[best] - pred_ts[pred_index]))
        if diff <= max_time_diff_s:
            pred_indices.append(pred_index)
            chosen.append(best)
            diffs.append(diff)

    pred_arr = np.asarray(pred_indices, dtype=np.int64)
    gt_arr = np.asarray(chosen, dtype=np.int64)
    return AlignedGtData(
        prediction_indices=pred_arr,
        gt_indices=gt_arr,
        prediction_timestamps=pred_ts[pred_arr] if pred_arr.size else np.empty(0, dtype=np.float64),
        gt_timestamps=gt_ts[gt_arr] if gt_arr.size else np.empty(0, dtype=np.float64),
        time_diffs_s=np.asarray(diffs, dtype=np.float64),
        gt_pose=gt_data.pose[gt_arr] if gt_arr.size else np.empty((0, 6), dtype=np.float64),
    )


def compute_gt_comparison(
    method_name: str,
    predicted_pose: np.ndarray,
    aligned_gt: AlignedGtData,
) -> tuple[dict[str, Any], dict[str, list[float]]]:
    """Compute absolute and relative pose metrics for one prediction method."""
    pred = np.asarray(predicted_pose, dtype=np.float64)
    if aligned_gt.prediction_indices.size == 0:
        return empty_gt_metrics(method_name), {}

    pred_aligned = pred[aligned_gt.prediction_indices]
    gt_aligned = aligned_gt.gt_pose
    finite = np.isfinite(pred_aligned).all(axis=1) & np.isfinite(gt_aligned).all(axis=1)
    pred_aligned = pred_aligned[finite]
    gt_aligned = gt_aligned[finite]
    timestamps = aligned_gt.prediction_timestamps[finite]
    time_diffs = aligned_gt.time_diffs_s[finite]
    if pred_aligned.shape[0] == 0:
        return empty_gt_metrics(method_name), {}

    translation_error = pred_aligned[:, 0:3] - gt_aligned[:, 0:3]
    translation_error_norm = np.linalg.norm(translation_error, axis=1)
    rotation_errors = rotation_error_batch(pred_aligned[:, 3:6], gt_aligned[:, 3:6])
    rpe_translation, rpe_rotation = relative_pose_errors(pred_aligned, gt_aligned)

    metrics = {
        f"{method_name}_matched_frames": int(pred_aligned.shape[0]),
        f"{method_name}_mean_time_diff_s": float(np.mean(time_diffs)) if time_diffs.size else None,
        f"{method_name}_max_time_diff_s": float(np.max(time_diffs)) if time_diffs.size else None,
        f"{method_name}_translation_rmse": vector_rmse(translation_error),
        f"{method_name}_ate": float(np.sqrt(np.mean(translation_error_norm**2))),
        f"{method_name}_rotation_error_mean_rad": float(np.mean(rotation_errors)),
        f"{method_name}_rotation_error_median_rad": float(np.median(rotation_errors)),
        f"{method_name}_rotation_error_max_rad": float(np.max(rotation_errors)),
        f"{method_name}_rpe_translation_mean": float(np.mean(rpe_translation)) if rpe_translation.size else 0.0,
        f"{method_name}_rpe_translation_median": float(np.median(rpe_translation)) if rpe_translation.size else 0.0,
        f"{method_name}_rpe_translation_max": float(np.max(rpe_translation)) if rpe_translation.size else 0.0,
        f"{method_name}_rpe_rotation_mean_rad": float(np.mean(rpe_rotation)) if rpe_rotation.size else 0.0,
        f"{method_name}_rpe_rotation_median_rad": float(np.median(rpe_rotation)) if rpe_rotation.size else 0.0,
        f"{method_name}_rpe_rotation_max_rad": float(np.max(rpe_rotation)) if rpe_rotation.size else 0.0,
        f"{method_name}_tx_rmse": scalar_rmse(translation_error[:, 0]),
        f"{method_name}_ty_rmse": scalar_rmse(translation_error[:, 1]),
        f"{method_name}_tz_rmse": scalar_rmse(translation_error[:, 2]),
        f"{method_name}_tx_mean_error": float(np.mean(translation_error[:, 0])),
        f"{method_name}_ty_mean_error": float(np.mean(translation_error[:, 1])),
        f"{method_name}_tz_mean_error": float(np.mean(translation_error[:, 2])),
    }
    series = {
        "timestamp": timestamps.tolist(),
        f"{method_name}_translation_error": translation_error_norm.tolist(),
        f"{method_name}_rotation_error_rad": rotation_errors.tolist(),
        f"{method_name}_tx_error": translation_error[:, 0].tolist(),
        f"{method_name}_ty_error": translation_error[:, 1].tolist(),
        f"{method_name}_tz_error": translation_error[:, 2].tolist(),
    }
    return metrics, series


def empty_gt_metrics(method_name: str) -> dict[str, Any]:
    """Return a complete empty metric block for a method with no GT matches."""
    return {
        f"{method_name}_matched_frames": 0,
        f"{method_name}_mean_time_diff_s": None,
        f"{method_name}_max_time_diff_s": None,
        f"{method_name}_translation_rmse": None,
        f"{method_name}_ate": None,
        f"{method_name}_rotation_error_mean_rad": None,
        f"{method_name}_rotation_error_median_rad": None,
        f"{method_name}_rotation_error_max_rad": None,
        f"{method_name}_rpe_translation_mean": None,
        f"{method_name}_rpe_translation_median": None,
        f"{method_name}_rpe_translation_max": None,
        f"{method_name}_rpe_rotation_mean_rad": None,
        f"{method_name}_rpe_rotation_median_rad": None,
        f"{method_name}_rpe_rotation_max_rad": None,
        f"{method_name}_tx_rmse": None,
        f"{method_name}_ty_rmse": None,
        f"{method_name}_tz_rmse": None,
        f"{method_name}_tx_mean_error": None,
        f"{method_name}_ty_mean_error": None,
        f"{method_name}_tz_mean_error": None,
    }


def rotation_error_batch(pred_rvec: np.ndarray, gt_rvec: np.ndarray) -> np.ndarray:
    """Compute geodesic rotation error from Rodrigues rotation vectors."""
    errors = []
    for pred, gt in zip(pred_rvec, gt_rvec):
        r_pred = rvec_to_matrix(pred)
        r_gt = rvec_to_matrix(gt)
        if r_pred is None or r_gt is None:
            errors.append(float("nan"))
            continue
        r_delta = r_gt.T @ r_pred
        cos_angle = np.clip((np.trace(r_delta) - 1.0) / 2.0, -1.0, 1.0)
        errors.append(float(np.arccos(cos_angle)))
    arr = np.asarray(errors, dtype=np.float64)
    return arr[np.isfinite(arr)]


def relative_pose_errors(pred_pose: np.ndarray, gt_pose: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compute one-step relative pose error arrays."""
    if pred_pose.shape[0] < 2 or gt_pose.shape[0] < 2:
        return np.empty(0, dtype=np.float64), np.empty(0, dtype=np.float64)
    trans_errors: list[float] = []
    rot_errors: list[float] = []
    for index in range(1, pred_pose.shape[0]):
        pred_delta_t = pred_pose[index, 0:3] - pred_pose[index - 1, 0:3]
        gt_delta_t = gt_pose[index, 0:3] - gt_pose[index - 1, 0:3]
        trans_errors.append(float(np.linalg.norm(pred_delta_t - gt_delta_t)))

        pred_prev_r = rvec_to_matrix(pred_pose[index - 1, 3:6])
        pred_curr_r = rvec_to_matrix(pred_pose[index, 3:6])
        gt_prev_r = rvec_to_matrix(gt_pose[index - 1, 3:6])
        gt_curr_r = rvec_to_matrix(gt_pose[index, 3:6])
        if pred_prev_r is None or pred_curr_r is None or gt_prev_r is None or gt_curr_r is None:
            rot_errors.append(float("nan"))
            continue
        pred_rel = pred_prev_r.T @ pred_curr_r
        gt_rel = gt_prev_r.T @ gt_curr_r
        rel_error = gt_rel.T @ pred_rel
        cos_angle = np.clip((np.trace(rel_error) - 1.0) / 2.0, -1.0, 1.0)
        rot_errors.append(float(np.arccos(cos_angle)))
    return _finite_array(trans_errors), _finite_array(rot_errors)


def rvec_to_matrix(rvec: np.ndarray) -> np.ndarray | None:
    """Convert Rodrigues vector to rotation matrix."""
    vec = np.asarray(rvec, dtype=np.float64).reshape(3)
    if not np.isfinite(vec).all():
        return None
    try:
        import cv2

        matrix, _ = cv2.Rodrigues(vec)
        return np.asarray(matrix, dtype=np.float64)
    except Exception:
        angle = float(np.linalg.norm(vec))
        if angle < 1e-12:
            return np.eye(3, dtype=np.float64)
        axis = vec / angle
        kx, ky, kz = axis
        k = np.array([[0, -kz, ky], [kz, 0, -kx], [-ky, kx, 0]], dtype=np.float64)
        return np.eye(3) + np.sin(angle) * k + (1.0 - np.cos(angle)) * (k @ k)


def vector_rmse(errors: np.ndarray) -> float:
    """RMSE of vector norm errors."""
    err = np.asarray(errors, dtype=np.float64)
    if err.size == 0:
        return 0.0
    norms = np.linalg.norm(err, axis=1) if err.ndim > 1 else np.abs(err)
    return float(np.sqrt(np.mean(norms**2)))


def scalar_rmse(errors: np.ndarray) -> float:
    """RMSE of scalar errors."""
    err = _finite_array(errors)
    if err.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(err**2)))


def _float_or_nan(value: str | None) -> float:
    if value is None or str(value).strip() == "":
        return float("nan")
    try:
        return float(value)
    except ValueError:
        return float("nan")


def _finite_array(values: Any) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    return arr[np.isfinite(arr)]
