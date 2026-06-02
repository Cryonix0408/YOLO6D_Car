"""位姿可视化与投影绘制工具。"""

from __future__ import annotations

import numpy as np

from .object_model import CUBOID_EDGES
from .pose.pnp import project_points
from .types import CameraIntrinsics, PoseSE3


def draw_pose_overlay(
    image_bgr: np.ndarray,
    object_points_xyz: np.ndarray,
    pose_camera_object: PoseSE3,
    intrinsics: CameraIntrinsics,
    color_bgr: tuple[int, int, int],
    label: str,
    edges: list[tuple[int, int]] | None = None,
) -> np.ndarray:
    """把 3D 模型投影到图像上，并绘制关键点、边和标签。"""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python is required for visualization.") from exc

    image = image_bgr.copy()
    # 先把 3D 模型点投影到当前图像，再用整数像素坐标绘制。
    projected = project_points(object_points_xyz, pose_camera_object, intrinsics)
    projected_i = np.round(projected).astype(int)

    for point in projected_i:
        cv2.circle(image, tuple(point), 4, color_bgr, -1)

    draw_edges = edges
    if draw_edges is None and projected_i.shape[0] >= 8:
        # 兼容立方体模型：未显式传边时使用默认长方体连线。
        draw_edges = CUBOID_EDGES

    if draw_edges is not None:
        for start_idx, end_idx in draw_edges:
            if 0 <= start_idx < len(projected_i) and 0 <= end_idx < len(projected_i):
                cv2.line(image, tuple(projected_i[start_idx]), tuple(projected_i[end_idx]), color_bgr, 2)

    anchor = tuple(projected_i[0]) if len(projected_i) else (20, 40)
    # 标签锚在第一个关键点上；没有点时退回固定位置。
    cv2.putText(
        image,
        label,
        anchor,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        color_bgr,
        2,
        cv2.LINE_AA,
    )
    return image
