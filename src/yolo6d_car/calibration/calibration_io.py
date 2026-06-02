"""本文件作用：
    管理 Hik 相机标定 session 的路径、JSON/YAML 写入和报告输出。

在 YOLO6D_Car pipeline 中的位置：
    calibration I/O 层。它不做角点检测或求解，只负责把结果安全写到 G 盘 outputs。

注意事项：
    默认不覆盖旧结果；如果目录已存在，调用方应选择时间戳 session 或显式 overwrite。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from yolo6d_car.path_utils import LocalPaths, resolve_path


def load_calibration_config(config_path: str | Path) -> dict[str, Any]:
    """Load a calibration YAML config."""
    path = Path(config_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Calibration config not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for section in ("camera", "calibration_board", "capture", "output"):
        if section not in raw or not isinstance(raw[section], dict):
            raise ValueError(f"Calibration config missing '{section}' mapping: {path}")
    return raw


def resolve_output_base(config: dict[str, Any], project_root: Path, local_paths: LocalPaths | None) -> Path:
    """Resolve the configured calibration output root."""
    output_root = resolve_path(config["output"].get("root", "outputs/calibration"), project_root=project_root, local_paths=local_paths)
    if output_root is None:
        raise ValueError("output.root is required")
    return output_root


def session_name(config: dict[str, Any]) -> str:
    """Return the configured base session name."""
    name = str(config["output"].get("session_name", "")).strip()
    if not name:
        lens = str(config["camera"].get("lens", "unknown")).replace(" ", "_")
        return f"hik_{lens}"
    return name


def choose_session_dir(base_root: Path, base_name: str, *, overwrite: bool = False) -> Path:
    """Choose a session directory without overwriting previous calibration results."""
    target = base_root / base_name
    if overwrite or not target.exists():
        return target
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return base_root / f"{base_name}_{timestamp}"


def ensure_session_dirs(session_dir: Path) -> dict[str, Path]:
    """Create standard calibration session subdirectories."""
    dirs = {
        "root": session_dir,
        "raw_images": session_dir / "raw_images",
        "debug_corners": session_dir / "debug_corners",
        "samples": session_dir / "samples",
        "undistort_check": session_dir / "undistort_check",
        "reprojection_error_visualization": session_dir / "reprojection_error_visualization",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write UTF-8 JSON with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_corners_json(path: Path, corners: np.ndarray) -> None:
    """Save corner coordinates as simple JSON for inspection."""
    points = np.asarray(corners, dtype=float).reshape(-1, 2)
    write_json(path, {"corners_px": points.tolist()})


def save_intrinsics_yaml(path: Path, *, config: dict[str, Any], result: dict[str, Any]) -> None:
    """Save camera intrinsics YAML compatible with downstream PnP usage."""
    camera_matrix = np.asarray(result["camera_matrix"], dtype=float).reshape(3, 3)
    dist = np.asarray(result["distortion_coefficients"], dtype=float).reshape(-1)
    coeffs = [float(x) for x in np.pad(dist, (0, max(0, 5 - dist.size)), mode="constant")[:5]]
    errors = result["per_view_reprojection_error"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "camera": {
            "name": config["camera"]["name"],
            "lens": config["camera"]["lens"],
            "width": int(result["image_size"][0]),
            "height": int(result["image_size"][1]),
        },
        "camera_matrix": {
            "fx": float(camera_matrix[0, 0]),
            "fy": float(camera_matrix[1, 1]),
            "cx": float(camera_matrix[0, 2]),
            "cy": float(camera_matrix[1, 2]),
            "matrix": camera_matrix.tolist(),
        },
        "distortion": {
            "model": "opencv_radial_tangential",
            "coefficients": {
                "k1": coeffs[0],
                "k2": coeffs[1],
                "p1": coeffs[2],
                "p2": coeffs[3],
                "k3": coeffs[4],
            },
            "vector": coeffs,
        },
        "calibration": {
            "board_type": config["calibration_board"]["type"],
            "pattern_cols": int(config["calibration_board"]["pattern_cols"]),
            "pattern_rows": int(config["calibration_board"]["pattern_rows"]),
            "square_size_mm": float(config["calibration_board"]["square_size_mm"]),
            "num_samples": int(result["number_of_samples"]),
            "rms_reprojection_error_px": float(result["rms_reprojection_error"]),
            "mean_reprojection_error_px": float(np.mean(errors)) if errors else 0.0,
            "max_reprojection_error_px": float(np.max(errors)) if errors else 0.0,
            "calibrated_at": now,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def save_report(path: Path, *, config: dict[str, Any], result: dict[str, Any], intrinsics_path: Path) -> None:
    """Write a markdown calibration report."""
    errors = result["per_view_reprojection_error"]
    mean_error = float(np.mean(errors)) if errors else 0.0
    max_error = float(np.max(errors)) if errors else 0.0
    rms = float(result["rms_reprojection_error"])
    warning = ""
    if rms > 1.0 or mean_error > 1.0:
        warning = (
            "\n## High Error Warning\n\n"
            "Reprojection error is high. Possible causes:\n\n"
            "- Calibration board square size is configured incorrectly.\n"
            "- Corner detection was unstable.\n"
            "- Images were blurry.\n"
            "- Sample poses were not diverse enough.\n"
            "- Lens focus or mounting changed during capture.\n"
            "- 6mm and 8mm lens configs or images were mixed.\n"
        )
    lines = [
        f"# Hik Camera Calibration Report - {config['camera']['lens']}",
        "",
        f"- Camera: `{config['camera']['name']}`",
        f"- Lens: `{config['camera']['lens']}`",
        f"- Intrinsics YAML: `{intrinsics_path.name}`",
        f"- Samples: {result['number_of_samples']}",
        f"- RMS reprojection error: {rms:.4f} px",
        f"- Mean per-view reprojection error: {mean_error:.4f} px",
        f"- Max per-view reprojection error: {max_error:.4f} px",
        "",
        "## Per-View Error",
        "",
    ]
    lines.extend(f"- sample {idx:03d}: {err:.4f} px" for idx, err in enumerate(errors))
    if warning:
        lines.append(warning)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
