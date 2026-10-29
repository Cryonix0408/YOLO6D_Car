"""不依赖 CLI 的 Mocap 刚体位姿查询与插值工具。"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import Protocol, Sequence

import numpy as np

from ..transforms import normalize_quaternion, quaternion_slerp


@dataclass(frozen=True, slots=True)
class RigidPose:
    """某一时刻的刚体位姿。

    四元数固定使用 ``xyzw`` 顺序。平移单位为米，时间单位为秒。
    """

    timestamp_s: float
    translation_m: np.ndarray
    quaternion_xyzw: np.ndarray
    valid: bool = True


class RigidPoseSample(Protocol):
    """插值函数所需的最小样本协议。"""

    timestamp_s: float
    translation_m: np.ndarray
    quaternion_xyzw: np.ndarray


def interpolate_rigid_pose(
    samples: Sequence[RigidPoseSample],
    query_timestamp_s: float,
    *,
    max_gap_s: float | None = None,
    allow_extrapolation: bool = False,
) -> RigidPose | None:
    """查询并插值刚体位姿。

    平移使用线性插值，旋转使用 ``xyzw`` 四元数 SLERP。默认禁止外推；
    相邻样本间隔超过 ``max_gap_s`` 时也返回 ``None``。
    """

    if not samples:
        return None
    if max_gap_s is not None and max_gap_s < 0:
        raise ValueError("max_gap_s must be non-negative or None")

    ordered = sorted(samples, key=lambda item: float(item.timestamp_s))
    timestamps = [float(item.timestamp_s) for item in ordered]
    query = float(query_timestamp_s)
    index = bisect.bisect_left(timestamps, query)

    # 完全相同时间戳直接返回该样本，重复时间戳保持稳定地选择第一条。
    if index < len(ordered) and timestamps[index] == query:
        sample = ordered[index]
        return RigidPose(
            timestamp_s=query,
            translation_m=np.asarray(sample.translation_m, dtype=np.float64).reshape(3).copy(),
            quaternion_xyzw=normalize_quaternion(sample.quaternion_xyzw),
        )

    if index == 0:
        if not allow_extrapolation or len(ordered) < 2:
            return None
        left_index, right_index = 0, 1
    elif index == len(ordered):
        if not allow_extrapolation or len(ordered) < 2:
            return None
        left_index, right_index = len(ordered) - 2, len(ordered) - 1
    else:
        left_index, right_index = index - 1, index

    left = ordered[left_index]
    right = ordered[right_index]
    left_time = float(left.timestamp_s)
    right_time = float(right.timestamp_s)
    gap_s = right_time - left_time
    if gap_s < 0:
        raise ValueError("samples must have monotonic timestamps after sorting")
    if max_gap_s is not None and gap_s > max_gap_s:
        return None
    if gap_s == 0.0:
        return RigidPose(
            timestamp_s=query,
            translation_m=np.asarray(left.translation_m, dtype=np.float64).reshape(3).copy(),
            quaternion_xyzw=normalize_quaternion(left.quaternion_xyzw),
        )

    alpha = (query - left_time) / gap_s
    left_translation = np.asarray(left.translation_m, dtype=np.float64).reshape(3)
    right_translation = np.asarray(right.translation_m, dtype=np.float64).reshape(3)
    translation = (1.0 - alpha) * left_translation + alpha * right_translation

    first = normalize_quaternion(left.quaternion_xyzw)
    second = normalize_quaternion(right.quaternion_xyzw)
    # q 与 -q 表示同一旋转；先统一到最短弧，避免错误绕行。
    if float(np.dot(first, second)) < 0.0:
        second = -second
    quaternion = quaternion_slerp(first, second, float(alpha))
    return RigidPose(query, translation, quaternion)


def nearest_rigid_pose(
    samples: Sequence[RigidPoseSample],
    query_timestamp_s: float,
    *,
    max_time_diff_s: float | None = None,
) -> RigidPose | None:
    """显式执行兼容的最近邻查询。"""

    if not samples:
        return None
    nearest = min(samples, key=lambda item: abs(float(item.timestamp_s) - query_timestamp_s))
    delta = abs(float(nearest.timestamp_s) - float(query_timestamp_s))
    if max_time_diff_s is not None and delta > max_time_diff_s:
        return None
    return RigidPose(
        timestamp_s=float(nearest.timestamp_s),
        translation_m=np.asarray(nearest.translation_m, dtype=np.float64).reshape(3).copy(),
        quaternion_xyzw=normalize_quaternion(nearest.quaternion_xyzw),
    )
