"""项目内部共享的数据结构定义。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass(slots=True)
class CameraIntrinsics:
    """保存相机内参，并提供 OpenCV 常用的相机矩阵。"""

    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int
    dist_coeffs: np.ndarray

    def camera_matrix(self) -> np.ndarray:
        """返回 3x3 相机内参矩阵。"""
        return np.array(
            [
                [self.fx, 0.0, self.cx],
                [0.0, self.fy, self.cy],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )


@dataclass(slots=True)
class ImageFrame:
    """统一封装一帧图像、深度、时间戳和内参。"""

    color: np.ndarray
    depth: Optional[np.ndarray]
    timestamp_s: float
    intrinsics: CameraIntrinsics


@dataclass(slots=True)
class KeypointDetection:
    """单个目标的 2D 关键点检测结果。"""

    label: str
    confidence: float
    image_points_px: np.ndarray
    keypoint_scores: Optional[np.ndarray] = None
    bbox_xyxy: Optional[np.ndarray] = None
    inference_mode: str = "full"


@dataclass(slots=True)
class PoseSE3:
    """表示一个 3D 刚体位姿。"""

    parent_frame: str
    child_frame: str
    rotation: np.ndarray
    translation_m: np.ndarray
    timestamp_s: Optional[float] = None

    def as_matrix(self) -> np.ndarray:
        """转换为 4x4 齐次变换矩阵。"""
        matrix = np.eye(4, dtype=np.float64)
        matrix[:3, :3] = self.rotation
        matrix[:3, 3] = self.translation_m
        return matrix


@dataclass(slots=True)
class PoseEstimate:
    """保存一次位姿估计的主要输出。"""

    pose: PoseSE3
    confidence: float
    reprojection_error_px: float
    num_inliers: int
    detection_label: str
    source: str
