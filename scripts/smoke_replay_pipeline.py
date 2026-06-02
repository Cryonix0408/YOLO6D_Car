"""本文件作用：
    运行一个不需要真实相机的短 replay smoke test。

在 YOLO6D_Car pipeline 中的位置：
    开发验证入口。它使用 json_replay 配置驱动 PosePipeline，确认配置加载、PnP、
    可选 Kalman、CSV 输出等核心链路没有被改坏。

主要输入：
    --config replay YAML；可选 --paths-config；可选 --kalman-config。

主要输出：
    终端 JSON 状态；如果传入 --output-dir 或 --output-csv，也会写 pose_results.csv。

注意事项：
    这个脚本不连接 D455/海康，不打开 GUI，不需要真实大数据，是最适合日常改代码后运行的检查。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
# 允许从项目根目录直接运行脚本，不需要先 pip install 本地包。
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.config import load_config
from yolo6d_car.path_utils import load_local_paths, resolve_path
from yolo6d_car.pipeline import PosePipeline
from yolo6d_car.tracking.pose_kalman_filter import load_pose_kalman_config


def parse_args() -> argparse.Namespace:
    """定义无相机 smoke test 参数，默认使用当前离线 replay 配置。"""
    parser = argparse.ArgumentParser(description="Run a short replay smoke test without opening D455 or GUI windows.")
    parser.add_argument(
        "--config",
        default=str(ROOT / "configs" / "fzmotion_fixed_camera_current_rigids.yaml"),
        help="Replay/json config to load. Defaults to the current offline config.",
    )
    parser.add_argument("--paths-config", default=None, help="Optional local paths YAML, e.g. configs/paths_local.yaml.")
    parser.add_argument("--kalman-config", default=None, help="Optional fixed Kalman YAML, e.g. configs/kalman_fixed.yaml.")
    parser.add_argument("--output-dir", default=None, help="Optional output directory for replay artifacts.")
    parser.add_argument("--output-csv", default=None, help="Optional CSV path. Defaults to output-dir/pose_results.csv when output-dir is set.")
    parser.add_argument("--validate-config", action="store_true", help="Validate replay config without running frames.")
    parser.add_argument("--max-frames", type=int, default=3, help="Number of replay frames to process.")
    return parser.parse_args()


def _resolve_cli_path(raw_path: str | None, paths_config: str | None) -> Path | None:
    """Resolve optional output paths with the same D/G-drive rules as configs."""
    if raw_path is None:
        return None
    local_paths = load_local_paths(paths_config) if paths_config else None
    return resolve_path(raw_path, project_root=ROOT, local_paths=local_paths)


def main() -> None:
    """加载 replay 配置，关闭窗口和默认 CSV，跑少量帧确认主链路健康。"""
    args = parse_args()
    if args.max_frames <= 0:
        raise SystemExit("--max-frames must be greater than 0")

    config = load_config(args.config, paths_config=args.paths_config)
    if config.yolo6d.backend.lower() != "json_replay":
        raise SystemExit("smoke_replay_pipeline.py expects a config with yolo6d.backend=json_replay")
    if args.validate_config:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "config": str(Path(args.config).resolve()),
                    "paths_config": None if args.paths_config is None else str(Path(args.paths_config).resolve()),
                    "replay_json_path": None if config.yolo6d.replay_json_path is None else str(config.yolo6d.replay_json_path),
                    "replay_json_exists": None if config.yolo6d.replay_json_path is None else config.yolo6d.replay_json_path.exists(),
                    "hardware_required": False,
                    "large_data_required": False,
                },
                ensure_ascii=False,
            )
        )
        return None

    # Smoke test 只验证 pipeline 逻辑，不打开 OpenCV 窗口，也不污染正式 CSV 日志。
    config.output.show_window = False
    config.output.print_json_lines = False
    output_dir = _resolve_cli_path(args.output_dir, args.paths_config)
    output_csv = _resolve_cli_path(args.output_csv, args.paths_config)
    if output_csv is None and output_dir is not None:
        output_csv = output_dir / "pose_results.csv"
    config.output.save_csv = output_csv

    kalman_config = load_pose_kalman_config(args.kalman_config) if args.kalman_config else None
    PosePipeline(config, kalman_config=kalman_config).run(max_frames=args.max_frames)
    print(
        json.dumps(
            {
                "status": "ok",
                "config": str(Path(args.config).resolve()),
                "kalman_config": None if args.kalman_config is None else str(Path(args.kalman_config).resolve()),
                "output_csv": None if output_csv is None else str(output_csv.resolve()),
                "frames_requested": args.max_frames,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
