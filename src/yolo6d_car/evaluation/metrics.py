"""本文件作用：
    提供 pose trajectory 评估的基础数值指标。

在 YOLO6D_Car pipeline 中的位置：
    evaluation 层，被 scripts/evaluate_pose_results.py 和 ablation 汇总调用。

核心概念：
    jitter: 相邻帧 pose 差分范数的 RMS，用来粗看轨迹抖动。
    velocity smoothness: translation velocity norm 的标准差，越小通常越平滑。
    acceleration smoothness: translation acceleration norm 的标准差，越小通常表示少突变。

注意事项：
    这些指标主要评估稳定性，不直接代表 6DoF 绝对准确度；绝对准确度需要 GT 对比。
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable

import numpy as np


def _as_array(values: np.ndarray | Iterable[float]) -> np.ndarray:
    """Convert values to a float64 NumPy array."""
    return np.asarray(values, dtype=np.float64)


def _finite_rows(values: np.ndarray) -> np.ndarray:
    """Keep finite rows from a 1D or 2D array."""
    arr = _as_array(values)
    if arr.ndim == 1:
        return arr[np.isfinite(arr)]
    return arr[np.isfinite(arr).all(axis=1)]


def _safe_dt(timestamps: np.ndarray) -> np.ndarray:
    """Return positive per-step dt, replacing invalid values with median/fallback."""
    ts = _as_array(timestamps).reshape(-1)
    if ts.size < 2:
        return np.empty(0, dtype=np.float64)
    dt = np.diff(ts)
    finite_positive = dt[np.isfinite(dt) & (dt > 1e-9)]
    fallback = float(np.median(finite_positive)) if finite_positive.size else 1.0
    dt[~np.isfinite(dt)] = fallback
    dt[dt <= 1e-9] = fallback
    return dt


def compute_velocity(values: np.ndarray, timestamps: np.ndarray) -> np.ndarray:
    """Compute first derivative of a trajectory."""
    vals = _as_array(values)
    if vals.shape[0] < 2:
        return np.empty((0, vals.shape[1] if vals.ndim > 1 else 1), dtype=np.float64)
    dt = _safe_dt(timestamps)
    deltas = np.diff(vals, axis=0)
    return deltas / dt[:, None]


def compute_acceleration(values: np.ndarray, timestamps: np.ndarray) -> np.ndarray:
    """Compute second derivative of a trajectory."""
    velocity = compute_velocity(values, timestamps)
    if velocity.shape[0] < 2:
        return np.empty((0, velocity.shape[1] if velocity.ndim > 1 else 1), dtype=np.float64)
    dt = _safe_dt(timestamps)[1:]
    return np.diff(velocity, axis=0) / dt[:, None]


def compute_jitter(values: np.ndarray) -> float:
    """计算简单 jitter：相邻帧差分向量范数的 RMS。

    参数：
        values: shape=(N, D) 的轨迹，例如 translation 或 rvec。

    返回：
        单个 float。值越大，帧间变化越剧烈；但快速真实运动也会增大该值。
    """
    vals = _finite_rows(_as_array(values))
    if vals.shape[0] < 2:
        return 0.0
    delta_norm = np.linalg.norm(np.diff(vals, axis=0), axis=1)
    return float(np.sqrt(np.mean(delta_norm**2)))


def compute_rmse(a: np.ndarray, b: np.ndarray) -> float:
    """Compute RMSE between two arrays over finite aligned entries."""
    arr_a = _as_array(a)
    arr_b = _as_array(b)
    mask = np.isfinite(arr_a) & np.isfinite(arr_b)
    if not np.any(mask):
        return 0.0
    diff = arr_a[mask] - arr_b[mask]
    return float(np.sqrt(np.mean(diff**2)))


def compute_mean_abs_delta(values: np.ndarray) -> float:
    """Compute mean absolute frame-to-frame delta."""
    vals = _finite_rows(_as_array(values))
    if vals.shape[0] < 2:
        return 0.0
    return float(np.mean(np.abs(np.diff(vals, axis=0))))


def summarize_tracking_states(states: Iterable[str]) -> dict[str, int]:
    """Count tracking states with stable keys for common Kalman states."""
    counter = Counter(str(state).strip() for state in states)
    summary = dict(counter)
    for key in ("INIT", "TRACKING", "PREDICT_ONLY", "LOST", "disabled", ""):
        summary.setdefault(key, 0)
    return summary


def norm_std(values: np.ndarray) -> float:
    """Return standard deviation of vector norms."""
    vals = _finite_rows(_as_array(values))
    if vals.size == 0:
        return 0.0
    if vals.ndim == 1:
        norms = np.abs(vals)
    else:
        norms = np.linalg.norm(vals, axis=1)
    return float(np.std(norms))
