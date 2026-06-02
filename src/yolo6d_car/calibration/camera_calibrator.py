"""本文件作用：
    从已保存的棋盘格样本执行 OpenCV 相机标定。

在 YOLO6D_Car pipeline 中的位置：
    calibration solve 阶段。它读取 corners 和原图尺寸，输出 camera_matrix、distortion、
    reprojection error 和 intrinsics YAML。

注意事项：
    square_size_mm 必须和真实标定板一致；如果尺寸写错，重投影误差可能看似可用，
    但 PnP 的尺度会错。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from .calibration_io import save_intrinsics_yaml, save_report, write_json


def make_chessboard_object_points(board_config: dict[str, Any]) -> np.ndarray:
    """Generate 3D object points for an inner-corner chessboard pattern."""
    cols = int(board_config["pattern_cols"])
    rows = int(board_config["pattern_rows"])
    square_size_m = float(board_config["square_size_mm"]) / 1000.0
    points = np.zeros((rows * cols, 3), dtype=np.float32)
    grid_x, grid_y = np.meshgrid(np.arange(cols, dtype=np.float32), np.arange(rows, dtype=np.float32))
    points[:, 0] = grid_x.reshape(-1) * square_size_m
    points[:, 1] = grid_y.reshape(-1) * square_size_m
    return points


def load_saved_samples(session_dir: Path) -> tuple[list[np.ndarray], list[np.ndarray], tuple[int, int], list[Path]]:
    """Load saved corner arrays and matching image sizes from a calibration session."""
    samples_dir = session_dir / "samples"
    sample_files = sorted(samples_dir.glob("sample_*_metadata.json"))
    image_points: list[np.ndarray] = []
    image_size: tuple[int, int] | None = None
    sample_paths: list[Path] = []

    for sample_path in sample_files:
        payload = json.loads(sample_path.read_text(encoding="utf-8"))
        corners_path = sample_path.with_name(str(payload.get("corners_npy", sample_path.stem + "_corners.npy")))
        if not corners_path.exists():
            continue
        corners = np.load(corners_path).astype(np.float32).reshape(-1, 1, 2)
        width = int(payload["image_size"]["width"])
        height = int(payload["image_size"]["height"])
        if image_size is None:
            image_size = (width, height)
        elif image_size != (width, height):
            raise ValueError(f"Mixed image sizes in calibration samples: {image_size} and {(width, height)}")
        image_points.append(corners)
        sample_paths.append(sample_path)

    if image_size is None:
        raise RuntimeError(f"No valid calibration samples found in: {samples_dir}")
    return image_points, [np.empty((0, 3), dtype=np.float32)] * len(image_points), image_size, sample_paths


def calibrate_from_session(session_dir: Path, config: dict[str, Any], *, overwrite: bool = False) -> dict[str, Any]:
    """Run OpenCV calibrateCamera from saved chessboard samples and write outputs."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python is required for camera calibration.") from exc

    image_points, _, image_size, sample_paths = load_saved_samples(session_dir)
    min_samples = int(config["capture"].get("min_samples", 30))
    if len(image_points) < min_samples:
        raise RuntimeError(f"Not enough samples for calibration: {len(image_points)} found, {min_samples} required")

    object_template = make_chessboard_object_points(config["calibration_board"])
    object_points = [object_template.copy() for _ in image_points]
    rms, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
        object_points,
        image_points,
        image_size,
        None,
        None,
    )

    per_view_errors: list[float] = []
    for obj_pts, img_pts, rvec, tvec in zip(object_points, image_points, rvecs, tvecs):
        projected, _ = cv2.projectPoints(obj_pts, rvec, tvec, camera_matrix, dist_coeffs)
        error = cv2.norm(img_pts, projected, cv2.NORM_L2) / len(projected)
        per_view_errors.append(float(error))

    result = {
        "camera_matrix": camera_matrix,
        "distortion_coefficients": dist_coeffs.reshape(-1),
        "rms_reprojection_error": float(rms),
        "per_view_reprojection_error": per_view_errors,
        "image_size": image_size,
        "number_of_samples": len(image_points),
        "sample_files": [str(path) for path in sample_paths],
    }

    lens = str(config["camera"]["lens"]).replace(" ", "_")
    intrinsics_path = session_dir / f"camera_intrinsics_hik_{lens}.yaml"
    report_path = session_dir / f"calibration_report_hik_{lens}.md"
    summary_path = session_dir / "calibration_summary.json"
    if not overwrite:
        for path in (intrinsics_path, report_path, summary_path):
            if path.exists():
                raise FileExistsError(f"Calibration output already exists. Use --overwrite to replace: {path}")

    save_intrinsics_yaml(intrinsics_path, config=config, result=result)
    save_report(report_path, config=config, result=result, intrinsics_path=intrinsics_path)
    write_json(
        summary_path,
        {
            "camera_matrix": camera_matrix.tolist(),
            "distortion_coefficients": dist_coeffs.reshape(-1).tolist(),
            "rms_reprojection_error": float(rms),
            "per_view_reprojection_error": per_view_errors,
            "image_size": {"width": image_size[0], "height": image_size[1]},
            "number_of_samples": len(image_points),
            "intrinsics_yaml": str(intrinsics_path),
            "report": str(report_path),
        },
    )
    _save_undistort_check(session_dir, camera_matrix, dist_coeffs)
    _save_reprojection_visualizations(session_dir, object_points, image_points, camera_matrix, dist_coeffs, rvecs, tvecs, per_view_errors, sample_paths)
    return result


def _save_undistort_check(session_dir: Path, camera_matrix: np.ndarray, dist_coeffs: np.ndarray) -> None:
    """Save one original/undistorted visual check image if raw samples exist."""
    try:
        import cv2
    except ImportError:
        return None

    raw_images = sorted((session_dir / "raw_images").glob("*.png"))
    if not raw_images:
        return None
    image = cv2.imread(str(raw_images[0]), cv2.IMREAD_COLOR)
    if image is None:
        return None
    undistorted = cv2.undistort(image, camera_matrix, dist_coeffs)
    out_dir = session_dir / "undistort_check"
    out_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_dir / "undistort_check_original.png"), image)
    cv2.imwrite(str(out_dir / "undistort_check_undistorted.png"), undistorted)
    return None


def _save_reprojection_visualizations(
    session_dir: Path,
    object_points: list[np.ndarray],
    image_points: list[np.ndarray],
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
    rvecs: tuple[np.ndarray, ...],
    tvecs: tuple[np.ndarray, ...],
    per_view_errors: list[float],
    sample_paths: list[Path],
) -> None:
    """Draw detected and reprojected corners for visual error inspection."""
    try:
        import cv2
    except ImportError:
        return None

    out_dir = session_dir / "reprojection_error_visualization"
    out_dir.mkdir(parents=True, exist_ok=True)
    for idx, (obj_pts, img_pts, rvec, tvec, error, sample_path) in enumerate(
        zip(object_points, image_points, rvecs, tvecs, per_view_errors, sample_paths),
        start=1,
    ):
        payload = json.loads(sample_path.read_text(encoding="utf-8"))
        image_path = Path(payload.get("image", ""))
        if not image_path.exists():
            continue
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            continue
        projected, _ = cv2.projectPoints(obj_pts, rvec, tvec, camera_matrix, dist_coeffs)
        observed = img_pts.reshape(-1, 2)
        projected = projected.reshape(-1, 2)
        for obs, pred in zip(observed, projected):
            obs_xy = (int(round(obs[0])), int(round(obs[1])))
            pred_xy = (int(round(pred[0])), int(round(pred[1])))
            cv2.circle(image, obs_xy, 3, (0, 255, 0), -1)
            cv2.circle(image, pred_xy, 3, (0, 0, 255), -1)
            cv2.line(image, obs_xy, pred_xy, (255, 0, 0), 1)
        cv2.putText(
            image,
            f"sample={idx:03d} reproj_error={error:.3f}px",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.imwrite(str(out_dir / f"sample_{idx:06d}_reprojection.png"), image)
    return None
