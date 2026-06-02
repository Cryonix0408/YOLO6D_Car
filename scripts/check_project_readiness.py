"""Offline readiness check for the YOLO6D_Car project skeleton."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.path_utils import load_local_paths


REQUIRED_DATA_DIRS = (
    "FZmotion_Data",
    "captures",
    "outputs",
    "outputs/object_capture",
    "outputs/auto_labels",
    "outputs/datasets",
    "outputs/train_runs",
    "outputs/calibration",
    "models",
    "results",
    "logs",
)

MAIN_SCRIPTS = (
    "scripts/calibrate_hik_camera.py",
    "scripts/sync_capture_to_host.py",
    "scripts/capture_object_samples.py",
    "scripts/capture_board_samples.py",
    "scripts/generate_mocap_labels.py",
    "scripts/batch_generate_mocap_labels.py",
    "scripts/prepare_yolo_pose_dataset.py",
    "scripts/train_ultralytics_pose.py",
    "scripts/smoke_replay_pipeline.py",
    "scripts/run_live_pose.py",
)

MAIN_CONFIGS = (
    "configs/paths_local.yaml",
    "configs/local_smoke_replay.yaml",
    "configs/local_smoke_replay_gdrive.yaml",
    "configs/calibration_hik_6mm.yaml",
    "configs/calibration_hik_8mm.yaml",
    "configs/object_capture_gdrive.yaml",
    "configs/board_capture_gdrive.yaml",
    "configs/fzmotion_fixed_camera_current_rigids_gdrive.yaml",
    "configs/uav_4m_20_sessions_gdrive.yaml",
    "configs/fzmotion_fixed_camera_live_v1_gdrive.yaml",
    "configs/kalman_fixed.yaml",
)


def parse_args() -> argparse.Namespace:
    """Parse readiness-check arguments."""
    parser = argparse.ArgumentParser(description="Check YOLO6D_Car project readiness without reading large data.")
    parser.add_argument("--paths-config", default="configs/paths_local.yaml", help="Local D/G-drive paths YAML.")
    return parser.parse_args()


def import_status(module_name: str) -> dict[str, object]:
    """Return import availability for a Python module."""
    try:
        module = importlib.import_module(module_name)
        return {"available": True, "version": getattr(module, "__version__", "unknown")}
    except Exception as exc:
        return {"available": False, "error": str(exc)}


def ultralytics_status() -> dict[str, object]:
    """Import Ultralytics with a temporary settings directory for permission-safe checks."""
    previous = os.environ.get("YOLO_CONFIG_DIR")
    with tempfile.TemporaryDirectory(prefix="yolo6d_ultralytics_") as tmp_dir:
        os.environ["YOLO_CONFIG_DIR"] = tmp_dir
        status = import_status("ultralytics")
    if previous is None:
        os.environ.pop("YOLO_CONFIG_DIR", None)
    else:
        os.environ["YOLO_CONFIG_DIR"] = previous
    return status


def torch_status() -> dict[str, object]:
    """Return PyTorch/CUDA availability without allocating large tensors."""
    try:
        import torch

        cuda_available = bool(torch.cuda.is_available())
        return {
            "available": True,
            "version": torch.__version__,
            "cuda_available": cuda_available,
            "cuda_device": torch.cuda.get_device_name(0) if cuda_available else None,
        }
    except Exception as exc:
        return {"available": False, "error": str(exc), "cuda_available": False}


def path_status(path: Path) -> dict[str, object]:
    """Describe a local path."""
    return {"path": str(path), "exists": path.exists(), "is_dir": path.is_dir() if path.exists() else None}


def main() -> None:
    """Run offline readiness checks and print a JSON summary."""
    args = parse_args()
    paths_config = Path(args.paths_config).resolve()
    local_paths = load_local_paths(paths_config)
    data_root = local_paths.data_root

    data_dirs = []
    mkdir_commands = []
    for rel in REQUIRED_DATA_DIRS:
        path = data_root / rel
        exists = path.exists()
        data_dirs.append({"relative": rel, "path": str(path), "exists": exists})
        if not exists:
            mkdir_commands.append(f"New-Item -ItemType Directory -Force -Path {path}")

    scripts = [{"path": rel, "exists": (ROOT / rel).exists()} for rel in MAIN_SCRIPTS]
    configs = [{"path": rel, "exists": (ROOT / rel).exists()} for rel in MAIN_CONFIGS]
    torch = torch_status()
    imports = {
        "ultralytics": ultralytics_status(),
        "cv2": import_status("cv2"),
        "yaml": import_status("yaml"),
        "numpy": import_status("numpy"),
        "scipy": import_status("scipy"),
    }

    missing_scripts = [item["path"] for item in scripts if not item["exists"]]
    missing_configs = [item["path"] for item in configs if not item["exists"]]
    missing_data_dirs = [item["relative"] for item in data_dirs if not item["exists"]]
    blocking = []
    if not paths_config.exists():
        blocking.append("paths_local.yaml is missing")
    if not local_paths.project_root.exists():
        blocking.append("project_root does not exist")
    if not data_root.exists():
        blocking.append("data_root does not exist")
    if missing_scripts:
        blocking.append("main scripts missing")
    if missing_configs:
        blocking.append("main configs missing")

    summary = {
        "python": {"executable": sys.executable, "version": sys.version.split()[0]},
        "project_root": path_status(local_paths.project_root),
        "current_root": str(ROOT),
        "data_root": path_status(data_root),
        "paths_config": path_status(paths_config),
        "torch": torch,
        "imports": imports,
        "data_dirs": data_dirs,
        "mkdir_commands_for_missing_data_dirs": mkdir_commands,
        "main_scripts": scripts,
        "main_configs": configs,
        "readiness_summary": {
            "status": "ready_for_skeleton_work" if not blocking else "needs_attention",
            "blocking": blocking,
            "missing_data_dirs": missing_data_dirs,
            "note": "Missing G-drive data directories are expected before real data collection; create them before capture/training.",
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
