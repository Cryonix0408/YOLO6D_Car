"""本文件作用：
    判断当前标定板画面是否值得保存为标定样本。

在 YOLO6D_Car pipeline 中的位置：
    calibration capture 阶段的质量门。

检查内容：
    blur_score、角点覆盖面积、board center/area/tilt 变化、采样时间间隔。

注意事项：
    目标是让样本覆盖中心、四角、近/远、倾斜和旋转姿态，避免连续保存几乎相同的图。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class QualityDecision:
    """Accept/reject decision for a detected calibration frame."""

    accept: bool
    reason: str
    blur_score: float
    coverage_ratio: float
    pose_delta: float
    board_center: tuple[float, float] | None = None
    board_bbox: tuple[float, float, float, float] | None = None
    board_area_ratio: float = 0.0
    nearest_center_shift: float = 0.0
    nearest_area_change: float = 0.0


def compute_blur_score(image_bgr: np.ndarray) -> float:
    """Compute image sharpness as Laplacian variance."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python is required for blur scoring.") from exc

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if image_bgr.ndim == 3 else image_bgr
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def compute_corner_coverage_ratio(corners: np.ndarray | None, image_shape: tuple[int, ...]) -> float:
    """Estimate board coverage by convex hull area divided by image area."""
    if corners is None:
        return 0.0
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python is required for corner coverage scoring.") from exc

    points = np.asarray(corners, dtype=np.float32).reshape(-1, 2)
    if points.shape[0] < 4:
        return 0.0
    hull = cv2.convexHull(points)
    hull_area = float(cv2.contourArea(hull))
    height, width = image_shape[:2]
    image_area = float(max(width * height, 1))
    return hull_area / image_area


def board_geometry(corners: np.ndarray | None, image_shape: tuple[int, ...]) -> dict[str, object]:
    """Compute center, bbox, and normalized area for detected board corners."""
    if corners is None:
        return {
            "center": None,
            "bbox": None,
            "area_ratio": 0.0,
        }
    points = np.asarray(corners, dtype=np.float32).reshape(-1, 2)
    height, width = image_shape[:2]
    x1 = float(np.min(points[:, 0]))
    y1 = float(np.min(points[:, 1]))
    x2 = float(np.max(points[:, 0]))
    y2 = float(np.max(points[:, 1]))
    center = ((x1 + x2) * 0.5 / max(width, 1), (y1 + y2) * 0.5 / max(height, 1))
    bbox = (x1, y1, x2, y2)
    area_ratio = ((x2 - x1) * (y2 - y1)) / float(max(width * height, 1))
    return {"center": center, "bbox": bbox, "area_ratio": float(area_ratio)}


def corner_pose_signature(corners: np.ndarray, image_shape: tuple[int, ...]) -> np.ndarray:
    """Build a compact signature for diversity checks between samples."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python is required for sample diversity scoring.") from exc

    points = np.asarray(corners, dtype=np.float32).reshape(-1, 2)
    height, width = image_shape[:2]
    center = points.mean(axis=0) / np.array([max(width, 1), max(height, 1)], dtype=np.float32)
    rect = cv2.minAreaRect(points)
    rect_w, rect_h = rect[1]
    scale = np.sqrt(max(rect_w * rect_h, 0.0) / float(max(width * height, 1)))
    angle = float(rect[2]) / 180.0
    first = points[0] / np.array([max(width, 1), max(height, 1)], dtype=np.float32)
    last = points[-1] / np.array([max(width, 1), max(height, 1)], dtype=np.float32)
    return np.array([center[0], center[1], scale, angle, first[0], first[1], last[0], last[1]], dtype=np.float64)


def similarity_metrics(signature: np.ndarray, previous_signatures: list[np.ndarray]) -> tuple[float, float, float]:
    """Return nearest full-signature, center, and area/scale changes."""
    if not previous_signatures:
        return float("inf"), float("inf"), float("inf")
    pose_distances = [float(np.linalg.norm(signature - prev)) for prev in previous_signatures]
    center_distances = [float(np.linalg.norm(signature[0:2] - prev[0:2])) for prev in previous_signatures]
    area_changes = [float(abs(signature[2] - prev[2]) / max(abs(prev[2]), 1e-6)) for prev in previous_signatures]
    return min(pose_distances), min(center_distances), min(area_changes)


def pose_delta_from_signatures(signature: np.ndarray, previous_signatures: list[np.ndarray]) -> float:
    """Return distance to the nearest previous sample signature."""
    if not previous_signatures:
        return float("inf")
    distances = [float(np.linalg.norm(signature - prev)) for prev in previous_signatures]
    return min(distances)


def evaluate_sample_quality(
    *,
    image_bgr: np.ndarray,
    detected: bool,
    corners: np.ndarray | None,
    capture_config: dict[str, Any],
    previous_signatures: list[np.ndarray],
    force_accept: bool = False,
) -> tuple[QualityDecision, np.ndarray | None]:
    """Evaluate blur, coverage, and view diversity for a candidate sample."""
    blur_score = compute_blur_score(image_bgr)
    coverage_ratio = compute_corner_coverage_ratio(corners, image_bgr.shape)
    geometry = board_geometry(corners, image_bgr.shape)
    center = geometry["center"]
    bbox = geometry["bbox"]
    area_ratio = float(geometry["area_ratio"])

    if not detected or corners is None:
        return QualityDecision(False, "board_not_detected", blur_score, coverage_ratio, 0.0, center, bbox, area_ratio), None

    signature = corner_pose_signature(corners, image_bgr.shape)
    pose_delta, center_shift, area_change = similarity_metrics(signature, previous_signatures)
    blur_threshold = float(capture_config.get("blur_threshold", 80.0))
    min_coverage = float(capture_config.get("min_corner_coverage_ratio", 0.25))
    min_pose_delta = float(capture_config.get("min_pose_delta", 0.08))
    min_center_shift = float(capture_config.get("min_center_shift_ratio", 0.08))
    min_area_change = float(capture_config.get("min_area_change_ratio", 0.20))

    if force_accept:
        return QualityDecision(True, "manual_save", blur_score, coverage_ratio, pose_delta, center, bbox, area_ratio, center_shift, area_change), signature
    if blur_score < blur_threshold:
        return QualityDecision(False, "image_too_blurry", blur_score, coverage_ratio, pose_delta, center, bbox, area_ratio, center_shift, area_change), signature
    if coverage_ratio < min_coverage:
        return QualityDecision(False, "board_coverage_too_small", blur_score, coverage_ratio, pose_delta, center, bbox, area_ratio, center_shift, area_change), signature
    if previous_signatures and pose_delta < min_pose_delta and center_shift < min_center_shift and area_change < min_area_change:
        return QualityDecision(False, "too similar to previous samples", blur_score, coverage_ratio, pose_delta, center, bbox, area_ratio, center_shift, area_change), signature
    return QualityDecision(True, "accepted", blur_score, coverage_ratio, pose_delta, center, bbox, area_ratio, center_shift, area_change), signature
