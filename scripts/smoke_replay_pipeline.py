"""Run a short no-camera replay smoke test for the 6DoF pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
# 允许从项目根目录直接运行脚本，无需先 pip install 本包。
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.config import load_config
from yolo6d_car.pipeline import PosePipeline


def parse_args() -> argparse.Namespace:
    """定义无相机烟测参数，默认使用当前离线 replay 配置。"""
    parser = argparse.ArgumentParser(description="Run a short replay smoke test without opening D455 or GUI windows.")
    parser.add_argument(
        "--config",
        default=str(ROOT / "configs" / "fzmotion_fixed_camera_current_rigids.yaml"),
        help="Replay/json config to load. Defaults to the current offline config.",
    )
    parser.add_argument("--max-frames", type=int, default=3, help="Number of replay frames to process.")
    return parser.parse_args()


def main() -> None:
    """加载 replay 配置，关闭窗口/日志落盘，跑少量帧确认主链路健康。"""
    args = parse_args()
    if args.max_frames <= 0:
        raise SystemExit("--max-frames must be greater than 0")

    config = load_config(args.config)
    if config.yolo6d.backend.lower() != "json_replay":
        raise SystemExit("smoke_replay_pipeline.py expects a config with yolo6d.backend=json_replay")

    # 烟测只验证 pipeline 逻辑，不弹 OpenCV 窗口，也不污染正式 CSV 日志。
    config.output.show_window = False
    config.output.print_json_lines = False
    config.output.save_csv = None

    PosePipeline(config).run(max_frames=args.max_frames)
    print(
        json.dumps(
            {
                "status": "ok",
                "config": str(Path(args.config).resolve()),
                "frames_requested": args.max_frames,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
