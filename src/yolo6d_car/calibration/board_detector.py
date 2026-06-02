"""本文件作用：
    检测标定板角点，目前第一版重点支持 chessboard。

在 YOLO6D_Car pipeline 中的位置：
    Hikrobot 标定 capture 阶段。只有检测到稳定、清晰、覆盖足够的角点，样本才会保存。

主要输入：
    相机图像和 calibration_board 配置。

主要输出：
    BoardDetection，包括 detected、corners 和 debug_info。

注意事项：
    pattern_cols / pattern_rows 指棋盘格内角点数量，不是方格数量。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class BoardDetection:
    """Result of one calibration board detection."""

    detected: bool
    corners: np.ndarray | None
    debug_info: dict[str, Any]


def detect_chessboard(image_bgr: np.ndarray, board_config: dict[str, Any]) -> BoardDetection:
    """Detect a full chessboard and refine inner corners to sub-pixel accuracy."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python is required for chessboard calibration.") from exc

    pattern_size = (int(board_config["pattern_cols"]), int(board_config["pattern_rows"]))
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if image_bgr.ndim == 3 else image_bgr
    debug: dict[str, Any] = {"board_type": "chessboard", "pattern_size": pattern_size, "method": None}

    detected = False
    corners = None
    if hasattr(cv2, "findChessboardCornersSB"):
        flags = cv2.CALIB_CB_NORMALIZE_IMAGE | cv2.CALIB_CB_EXHAUSTIVE
        detected, corners = cv2.findChessboardCornersSB(gray, pattern_size, flags)
        debug["method"] = "findChessboardCornersSB"

    if not detected:
        flags = cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE
        detected, corners = cv2.findChessboardCorners(gray, pattern_size, flags)
        debug["method"] = "findChessboardCorners"
        if detected and corners is not None:
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.001)
            corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

    if not detected or corners is None:
        debug["num_corners"] = 0
        return BoardDetection(detected=False, corners=None, debug_info=debug)

    refined = np.asarray(corners, dtype=np.float32).reshape(-1, 1, 2)
    debug["num_corners"] = int(refined.shape[0])
    return BoardDetection(detected=True, corners=refined, debug_info=debug)


def detect_board(image_bgr: np.ndarray, board_config: dict[str, Any]) -> BoardDetection:
    """Dispatch to the configured calibration board detector."""
    board_type = str(board_config.get("type", "chessboard")).lower()
    if board_type != "chessboard":
        raise NotImplementedError(f"Unsupported calibration board type in this baseline: {board_type}")
    return detect_chessboard(image_bgr, board_config)


def draw_chessboard_debug(image_bgr: np.ndarray, board_config: dict[str, Any], detection: BoardDetection) -> np.ndarray:
    """Return an image with detected chessboard corners and status text drawn on it."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python is required for chessboard debug drawing.") from exc

    canvas = image_bgr.copy()
    pattern_size = (int(board_config["pattern_cols"]), int(board_config["pattern_rows"]))
    if detection.corners is not None:
        cv2.drawChessboardCorners(canvas, pattern_size, detection.corners, detection.detected)
    return canvas
