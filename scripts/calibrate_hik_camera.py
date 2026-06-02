"""本文件作用：
    采集并标定 Hikrobot MV-CS016-10UC 的镜头内参。

在 YOLO6D_Car pipeline 中的位置：
    calibration 阶段。标定输出 camera_intrinsics_*.yaml 后，PnP 才能把 2D keypoints
    正确恢复成 6DoF pose。

主要输入：
    configs/calibration_hik_6mm.yaml 或 configs/calibration_hik_8mm.yaml。

主要输出：
    outputs/calibration/hik_6mm 或 hik_8mm 下的 intrinsics YAML、报告、debug 图。

注意事项：
    6mm 和 8mm 内参不同，必须分别标定；不要混用镜头和 intrinsics。
    validate-config 不连接相机，capture/capture_and_calibrate 才需要实验室硬件。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.calibration.calibration_capture import run_capture_session
from yolo6d_car.calibration.calibration_io import (
    choose_session_dir,
    load_calibration_config,
    resolve_output_base,
    session_name,
)
from yolo6d_car.calibration.camera_calibrator import calibrate_from_session
from yolo6d_car.path_utils import load_local_paths


def parse_args() -> argparse.Namespace:
    """Parse Hik camera calibration CLI arguments."""
    parser = argparse.ArgumentParser(description="Capture and calibrate Hikrobot camera intrinsics.")
    parser.add_argument("--config", required=True, help="Calibration YAML, e.g. configs/calibration_hik_6mm.yaml.")
    parser.add_argument("--paths-config", default=None, help="Optional local paths YAML, e.g. configs/paths_local.yaml.")
    parser.add_argument("--validate-config", action="store_true", help="Alias for --mode validate_config.")
    parser.add_argument(
        "--mode",
        default=None,
        choices=("validate_config", "capture", "calibrate", "capture_and_calibrate"),
        help="Run validation, capture only, calibrate existing samples, or both.",
    )
    parser.add_argument(
        "--session-dir",
        default=None,
        help="Optional existing/output session directory. For calibrate mode, defaults to output.root/session_name.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing calibration result files in a session.")
    return parser.parse_args()


def _resolve_session_dir(args: argparse.Namespace, config: dict, *, for_capture: bool) -> Path:
    """Resolve or choose a calibration session directory."""
    local_paths = load_local_paths(args.paths_config) if args.paths_config else None
    if args.session_dir:
        return Path(args.session_dir).expanduser().resolve()
    base_root = resolve_output_base(config, ROOT, local_paths)
    if for_capture:
        return choose_session_dir(base_root, session_name(config), overwrite=args.overwrite)
    return base_root / session_name(config)


def validate_config(args: argparse.Namespace, config: dict) -> dict[str, object]:
    """Validate config and dependencies without opening a camera."""
    local_paths = load_local_paths(args.paths_config) if args.paths_config else None
    output_root = resolve_output_base(config, ROOT, local_paths)

    try:
        import cv2

        cv2_status = f"ok {cv2.__version__}"
    except ImportError:
        cv2_status = "missing opencv-python"

    board = config["calibration_board"]
    if str(board.get("type", "")).lower() != "chessboard":
        raise ValueError("First calibration baseline requires calibration_board.type='chessboard'")
    if int(board.get("pattern_cols", 0)) <= 0 or int(board.get("pattern_rows", 0)) <= 0:
        raise ValueError("pattern_cols and pattern_rows must be positive")
    if float(board.get("square_size_mm", 0.0)) <= 0.0:
        raise ValueError("square_size_mm must be positive")

    payload = {
        "status": "ok",
        "config": str(Path(args.config).resolve()),
        "paths_config": None if args.paths_config is None else str(Path(args.paths_config).resolve()),
        "camera": config["camera"],
        "board": config["calibration_board"],
        "output_root": str(output_root),
        "default_session_dir": str(output_root / session_name(config)),
        "opencv": cv2_status,
        "output_root_exists": output_root.exists(),
        "output_parent_exists": output_root.parent.exists(),
        "gitignore_note": "outputs/ is ignored; calibration images under G-drive outputs should not be committed.",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not cv2_status.startswith("ok"):
        raise SystemExit("opencv-python is required before capture/calibrate modes can run.")
    return payload


def main() -> None:
    """Run the selected calibration mode."""
    args = parse_args()
    if args.validate_config:
        args.mode = "validate_config"
    if args.mode is None:
        raise SystemExit("--mode is required unless --validate-config is used")
    config = load_calibration_config(args.config)

    if args.mode == "validate_config":
        validate_config(args, config)
        return None

    session_dir = _resolve_session_dir(args, config, for_capture=args.mode in {"capture", "capture_and_calibrate"})
    if args.mode == "capture":
        capture_result = run_capture_session(session_dir, config)
        print(
            json.dumps(
                {
                    "status": "capture_complete",
                    "session_dir": str(session_dir),
                    "saved_samples": capture_result.saved_samples,
                    "should_calibrate": capture_result.should_calibrate,
                    "stopped_reason": capture_result.stopped_reason,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return None

    if args.mode == "calibrate":
        result = calibrate_from_session(session_dir, config, overwrite=args.overwrite)
        print(
            json.dumps(
                {
                    "status": "calibration_complete",
                    "session_dir": str(session_dir),
                    "rms_reprojection_error": result["rms_reprojection_error"],
                    "number_of_samples": result["number_of_samples"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return None

    if args.mode == "capture_and_calibrate":
        capture_result = run_capture_session(session_dir, config)
        if not capture_result.should_calibrate:
            print(
                json.dumps(
                    {
                        "status": "capture_complete_without_calibration",
                        "session_dir": str(session_dir),
                        "saved_samples": capture_result.saved_samples,
                        "stopped_reason": capture_result.stopped_reason,
                        "message": "Not enough accepted samples or user quit before calibration.",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return None
        result = calibrate_from_session(session_dir, config, overwrite=args.overwrite)
        print(
            json.dumps(
                {
                    "status": "capture_and_calibration_complete",
                    "session_dir": str(session_dir),
                    "capture_stopped_reason": capture_result.stopped_reason,
                    "rms_reprojection_error": result["rms_reprojection_error"],
                    "number_of_samples": result["number_of_samples"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return None

    raise SystemExit(f"Unsupported mode: {args.mode}")


if __name__ == "__main__":
    main()
