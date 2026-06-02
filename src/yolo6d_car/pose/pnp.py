"""基于 2D/3D 对应点的 PnP 求解与重投影工具。"""

from __future__ import annotations

import numpy as np

from ..config import PnPConfig
from ..types import CameraIntrinsics, KeypointDetection, PoseEstimate, PoseSE3


def project_points(
    object_points_xyz: np.ndarray,
    pose_camera_object: PoseSE3,
    intrinsics: CameraIntrinsics,
) -> np.ndarray:
    """将 3D 模型点投影到图像平面。"""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python is required for PnP projection.") from exc

    # OpenCV projectPoints 使用 rvec/tvec 表示相机坐标系下的物体位姿。
    rvec, _ = cv2.Rodrigues(pose_camera_object.rotation)
    image_points, _ = cv2.projectPoints(
        np.asarray(object_points_xyz, dtype=np.float64),
        rvec,
        pose_camera_object.translation_m.reshape(3, 1),
        intrinsics.camera_matrix(),
        intrinsics.dist_coeffs,
    )
    return image_points.reshape(-1, 2)


def _compute_reprojection_error(
    object_points_xyz: np.ndarray,
    image_points_px: np.ndarray,
    pose_camera_object: PoseSE3,
    intrinsics: CameraIntrinsics,
) -> float:
    """计算当前位姿下的均方根重投影误差。"""
    projected = project_points(object_points_xyz, pose_camera_object, intrinsics)
    deltas = projected - image_points_px
    return float(np.sqrt(np.mean(np.sum(deltas * deltas, axis=1))))


def solve_pose_from_detection(
    detection: KeypointDetection,
    object_points_xyz: np.ndarray,
    intrinsics: CameraIntrinsics,
    pnp_config: PnPConfig,
) -> PoseEstimate | None:
    """根据一次关键点检测结果求解 6DoF 位姿。"""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python is required for pose estimation.") from exc

    image_points = np.asarray(detection.image_points_px, dtype=np.float64).reshape(-1, 2)
    object_points = np.asarray(object_points_xyz, dtype=np.float64).reshape(-1, 3)

    if image_points.shape[0] != object_points.shape[0]:
        raise ValueError(
            f"2D/3D keypoint count mismatch: {image_points.shape[0]} image points vs "
            f"{object_points.shape[0]} object points."
        )

    valid_mask = np.isfinite(image_points).all(axis=1)
    if detection.keypoint_scores is not None:
        # 低置信度关键点不参与 PnP，避免拖坏整体位姿。
        keypoint_scores = np.asarray(detection.keypoint_scores, dtype=np.float64).reshape(-1)
        if keypoint_scores.shape[0] != image_points.shape[0]:
            raise ValueError("keypoint_scores length must match image_points length.")
        valid_mask &= keypoint_scores >= pnp_config.min_keypoint_score

    valid_image_points = image_points[valid_mask]
    valid_object_points = object_points[valid_mask]
    if valid_image_points.shape[0] < 4:
        # PnP 至少需要 4 对 2D/3D 点。
        return None

    # RANSAC 先剔除离群关键点，再求解一个稳健初值。
    success, rvec, tvec, inliers = cv2.solvePnPRansac(
        objectPoints=valid_object_points,
        imagePoints=valid_image_points,
        cameraMatrix=intrinsics.camera_matrix(),
        distCoeffs=intrinsics.dist_coeffs,
        reprojectionError=pnp_config.ransac_reproj_threshold_px,
        iterationsCount=pnp_config.iterations_count,
        confidence=pnp_config.confidence,
        flags=cv2.SOLVEPNP_EPNP,
    )
    if not success:
        return None

    # 先用 RANSAC 求初值，再尝试用 LM 做局部细化。
    if hasattr(cv2, "solvePnPRefineLM"):
        try:
            rvec, tvec = cv2.solvePnPRefineLM(
                valid_object_points,
                valid_image_points,
                intrinsics.camera_matrix(),
                intrinsics.dist_coeffs,
                rvec,
                tvec,
            )
        except cv2.error:
            pass

    rotation, _ = cv2.Rodrigues(rvec)
    # PnP 输出的是 T_camera_object_model。
    pose = PoseSE3(
        parent_frame="camera_optical",
        child_frame=detection.label,
        rotation=rotation,
        translation_m=tvec.reshape(3),
    )
    reprojection_error_px = _compute_reprojection_error(
        valid_object_points,
        valid_image_points,
        pose,
        intrinsics,
    )
    num_inliers = int(0 if inliers is None else len(inliers))
    return PoseEstimate(
        pose=pose,
        confidence=float(detection.confidence),
        reprojection_error_px=reprojection_error_px,
        num_inliers=num_inliers,
        detection_label=detection.label,
        source="yolo6d+pnp",
    )
