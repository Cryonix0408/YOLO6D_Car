"""位姿、旋转矩阵和四元数之间的变换工具。"""

from __future__ import annotations

import math

import numpy as np

from .types import PoseSE3


def normalize_quaternion(quaternion_xyzw: np.ndarray) -> np.ndarray:
    """将输入四元数归一化。"""
    quaternion = np.asarray(quaternion_xyzw, dtype=np.float64).reshape(4)
    norm = np.linalg.norm(quaternion)
    if norm == 0.0:
        raise ValueError("Quaternion norm cannot be zero.")
    return quaternion / norm


def quaternion_to_matrix(quaternion_xyzw: np.ndarray) -> np.ndarray:
    """四元数转旋转矩阵。"""
    x, y, z, w = normalize_quaternion(quaternion_xyzw)
    # 手写公式避免引入 scipy 作为核心运行时强依赖。
    xx = x * x
    yy = y * y
    zz = z * z
    xy = x * y
    xz = x * z
    yz = y * z
    wx = w * x
    wy = w * y
    wz = w * z

    return np.array(
        [
            [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)],
            [2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)],
            [2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)],
        ],
        dtype=np.float64,
    )


def matrix_to_quaternion(rotation: np.ndarray) -> np.ndarray:
    """旋转矩阵转四元数。"""
    matrix = np.asarray(rotation, dtype=np.float64).reshape(3, 3)
    trace = np.trace(matrix)

    # 根据矩阵 trace 选择数值稳定的分支。
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        w = 0.25 * s
        x = (matrix[2, 1] - matrix[1, 2]) / s
        y = (matrix[0, 2] - matrix[2, 0]) / s
        z = (matrix[1, 0] - matrix[0, 1]) / s
    elif matrix[0, 0] > matrix[1, 1] and matrix[0, 0] > matrix[2, 2]:
        s = math.sqrt(1.0 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2]) * 2.0
        w = (matrix[2, 1] - matrix[1, 2]) / s
        x = 0.25 * s
        y = (matrix[0, 1] + matrix[1, 0]) / s
        z = (matrix[0, 2] + matrix[2, 0]) / s
    elif matrix[1, 1] > matrix[2, 2]:
        s = math.sqrt(1.0 + matrix[1, 1] - matrix[0, 0] - matrix[2, 2]) * 2.0
        w = (matrix[0, 2] - matrix[2, 0]) / s
        x = (matrix[0, 1] + matrix[1, 0]) / s
        y = 0.25 * s
        z = (matrix[1, 2] + matrix[2, 1]) / s
    else:
        s = math.sqrt(1.0 + matrix[2, 2] - matrix[0, 0] - matrix[1, 1]) * 2.0
        w = (matrix[1, 0] - matrix[0, 1]) / s
        x = (matrix[0, 2] + matrix[2, 0]) / s
        y = (matrix[1, 2] + matrix[2, 1]) / s
        z = 0.25 * s

    return normalize_quaternion(np.array([x, y, z, w], dtype=np.float64))


def quaternion_slerp(first_xyzw: np.ndarray, second_xyzw: np.ndarray, alpha: float) -> np.ndarray:
    """对两个四元数做球面线性插值。"""
    q0 = normalize_quaternion(first_xyzw)
    q1 = normalize_quaternion(second_xyzw)
    t = float(np.clip(alpha, 0.0, 1.0))

    dot = float(np.dot(q0, q1))
    if dot < 0.0:
        # q 和 -q 表示同一旋转；翻转后沿最短弧插值。
        q1 = -q1
        dot = -dot

    if dot > 0.9995:
        # 两个旋转非常接近时，用线性插值更稳定。
        blended = q0 + t * (q1 - q0)
        return normalize_quaternion(blended)

    theta_0 = math.acos(np.clip(dot, -1.0, 1.0))
    sin_theta_0 = math.sin(theta_0)
    if sin_theta_0 < 1e-8:
        return q0

    theta = theta_0 * t
    sin_theta = math.sin(theta)
    s0 = math.cos(theta) - dot * sin_theta / sin_theta_0
    s1 = sin_theta / sin_theta_0
    return normalize_quaternion((s0 * q0) + (s1 * q1))


def rotation_angle_deg(first: np.ndarray, second: np.ndarray) -> float:
    """计算两个旋转矩阵之间的夹角，单位为度。"""
    r_first = np.asarray(first, dtype=np.float64).reshape(3, 3)
    r_second = np.asarray(second, dtype=np.float64).reshape(3, 3)
    delta = r_first.T @ r_second
    cos_theta = np.clip((np.trace(delta) - 1.0) * 0.5, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_theta)))


def matrix_to_euler_xyz_deg(rotation: np.ndarray) -> np.ndarray:
    """旋转矩阵转 XYZ 欧拉角，单位为度。"""
    matrix = np.asarray(rotation, dtype=np.float64).reshape(3, 3)

    sy = math.sqrt(matrix[0, 0] * matrix[0, 0] + matrix[1, 0] * matrix[1, 0])
    singular = sy < 1e-6

    if not singular:
        x = math.atan2(matrix[2, 1], matrix[2, 2])
        y = math.atan2(-matrix[2, 0], sy)
        z = math.atan2(matrix[1, 0], matrix[0, 0])
    else:
        x = math.atan2(-matrix[1, 2], matrix[1, 1])
        y = math.atan2(-matrix[2, 0], sy)
        z = 0.0

    return np.degrees(np.array([x, y, z], dtype=np.float64))




def pose_from_quaternion_translation(
    parent_frame: str,
    child_frame: str,
    translation_m: np.ndarray,
    quaternion_xyzw: np.ndarray,
    timestamp_s: float | None = None,
) -> PoseSE3:
    """由平移和四元数构造 PoseSE3。"""
    return PoseSE3(
        parent_frame=parent_frame,
        child_frame=child_frame,
        rotation=quaternion_to_matrix(quaternion_xyzw),
        translation_m=np.asarray(translation_m, dtype=np.float64).reshape(3),
        timestamp_s=timestamp_s,
    )


def pose_from_matrix(
    parent_frame: str,
    child_frame: str,
    matrix: np.ndarray,
    timestamp_s: float | None = None,
) -> PoseSE3:
    """由 4x4 变换矩阵构造 PoseSE3。"""
    transform = np.asarray(matrix, dtype=np.float64).reshape(4, 4)
    return PoseSE3(
        parent_frame=parent_frame,
        child_frame=child_frame,
        rotation=transform[:3, :3].copy(),
        translation_m=transform[:3, 3].copy(),
        timestamp_s=timestamp_s,
    )


def compose_poses(first: PoseSE3, second: PoseSE3) -> PoseSE3:
    """按坐标系链式关系做位姿复合。"""
    if first.child_frame != second.parent_frame:
        # 坐标系名不匹配时直接报错，防止 silently 乘错矩阵。
        raise ValueError(
            f"Frame mismatch: cannot compose {first.parent_frame}->{first.child_frame} "
            f"with {second.parent_frame}->{second.child_frame}."
        )

    matrix = first.as_matrix() @ second.as_matrix()
    # 复合后优先保留后一个 pose 的时间戳，更贴近“当前被变换对象”的时间。
    timestamp_s = second.timestamp_s if second.timestamp_s is not None else first.timestamp_s
    return pose_from_matrix(first.parent_frame, second.child_frame, matrix, timestamp_s)


def invert_pose(pose: PoseSE3) -> PoseSE3:
    """求一个位姿的逆变换。"""
    rotation_inv = pose.rotation.T
    translation_inv = -rotation_inv @ pose.translation_m
    return PoseSE3(
        parent_frame=pose.child_frame,
        child_frame=pose.parent_frame,
        rotation=rotation_inv,
        translation_m=translation_inv,
        timestamp_s=pose.timestamp_s,
    )


def transform_points(pose: PoseSE3, points_xyz: np.ndarray) -> np.ndarray:
    """用位姿变换一组 3D 点。"""
    points = np.asarray(points_xyz, dtype=np.float64).reshape(-1, 3)
    return (pose.rotation @ points.T).T + pose.translation_m


