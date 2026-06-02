"""面向实机部署的实时 6DoF 入口脚本。"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.config import ProjectConfig, load_config
from yolo6d_car.path_utils import load_local_paths, resolve_path
from yolo6d_car.pipeline import PosePipeline


DEFAULT_CONFIG = ROOT / "configs" / "fzmotion_fixed_camera_live_v1.yaml"


def _resolve_root_path(raw_path: str | None, paths_config: str | None = None) -> Path | None:
    """把命令行传入的相对路径解析成项目根目录下的绝对路径。"""
    local_paths = load_local_paths(paths_config) if paths_config else None
    return resolve_path(raw_path, project_root=ROOT, local_paths=local_paths)


def parse_args() -> argparse.Namespace:
    """定义实时推理常用覆盖参数，避免为了临时调参频繁改 YAML。"""
    parser = argparse.ArgumentParser(description="Run live YOLO6D pose on the real machine.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="实时配置 YAML，默认使用正式 v1 配置。")
    parser.add_argument("--paths-config", default=None, help="Optional local paths YAML, e.g. configs/paths_local.yaml.")
    parser.add_argument("--validate-config", action="store_true", help="Validate config and paths without opening camera or loading model.")
    parser.add_argument("--model", default=None, help="可选：临时覆盖模型权重路径。")
    parser.add_argument("--device", default=None, help="可选：推理设备，如 0、cpu。")
    parser.add_argument("--imgsz", type=int, default=None, help="可选：推理输入尺寸。")
    parser.add_argument("--conf", type=float, default=None, help="可选：检测置信度阈值。")
    parser.add_argument("--fps", type=int, default=None, help="可选：临时覆盖 D455 采样帧率。")
    parser.add_argument("--save-csv", default=None, help="可选：实时日志 CSV 输出路径。")
    parser.add_argument("--no-save-csv", action="store_true", help="关闭 CSV 落盘。")
    parser.add_argument("--headless", action="store_true", help="不显示窗口，只保留终端 / CSV 输出。")
    parser.add_argument("--show-window", action="store_true", help="强制显示窗口。")
    parser.add_argument("--quiet-json", action="store_true", help="关闭终端 JSON 行输出。")
    parser.add_argument("--print-json", action="store_true", help="强制打开终端 JSON 行输出。")
    parser.add_argument("--disable-depth", action="store_true", help="关闭 D455 深度流，降低实机链路复杂度。")
    parser.add_argument("--enable-depth", action="store_true", help="强制开启 D455 深度流。")
    parser.add_argument("--enable-mocap", action="store_true", help="启用 mocap 对比。")
    parser.add_argument("--disable-mocap", action="store_true", help="关闭 mocap 对比。")
    parser.add_argument("--csv-path", default=None, help="当启用 mocap 时，指定 CSV 路径。")
    parser.add_argument("--max-frames", type=int, default=None, help="可选：最多处理多少帧，用于调试。")
    return parser.parse_args()


def validate_live_config(args: argparse.Namespace) -> None:
    """Validate live inference config without opening camera or loading model weights."""
    config = load_config(args.config, paths_config=args.paths_config)
    if args.model:
        model_path = _resolve_root_path(args.model, args.paths_config)
        if model_path is not None:
            config.yolo6d.model_path = model_path
    print(
        {
            "status": "ok",
            "script": Path(__file__).name,
            "config": str(Path(args.config).resolve()),
            "paths_config": None if args.paths_config is None else str(Path(args.paths_config).resolve()),
            "backend": config.yolo6d.backend,
            "model_path": None if config.yolo6d.model_path is None else str(config.yolo6d.model_path),
            "model_exists": None if config.yolo6d.model_path is None else config.yolo6d.model_path.exists(),
            "camera": f"{config.camera.source} {config.camera.color_width}x{config.camera.color_height}@{config.camera.fps}",
            "hardware_required": False,
            "large_data_required": False,
        }
    )


def apply_overrides(config: ProjectConfig, args: argparse.Namespace) -> None:
    """把命令行参数覆盖到强类型配置对象上。"""
    # 模型路径最容易在现场切换，所以允许通过 --model 临时覆盖。
    model_path = _resolve_root_path(args.model, args.paths_config)
    if model_path is not None:
        config.yolo6d.model_path = model_path

    # 推理参数属于无状态配置，可以直接覆盖，不影响原始 YAML 文件。
    if args.device is not None:
        config.yolo6d.inference_device = args.device
    if args.imgsz is not None:
        config.yolo6d.inference_imgsz = int(args.imgsz)
    if args.conf is not None:
        config.yolo6d.conf_threshold = float(args.conf)
    if args.fps is not None:
        config.camera.fps = int(args.fps)

    # 深度流不是当前 PnP 主链路必需项；现场不稳定时允许一键关闭。
    if args.disable_depth:
        config.camera.enable_depth = False
        config.camera.align_depth_to_color = False
    elif args.enable_depth:
        config.camera.enable_depth = True

    # headless 用于远程/批量调试；show-window 用于现场观察叠加结果。
    if args.headless:
        config.output.show_window = False
    elif args.show_window:
        config.output.show_window = True

    # CSV 日志通常用于后处理；现场只看窗口时可以关掉落盘。
    if args.no_save_csv:
        config.output.save_csv = None
    else:
        save_csv = _resolve_root_path(args.save_csv, args.paths_config)
        if save_csv is not None:
            config.output.save_csv = save_csv

    if args.quiet_json:
        config.output.print_json_lines = False
    elif args.print_json:
        config.output.print_json_lines = True

    # Mocap 对比在调试时很有用，但纯实时演示可以关闭以减少依赖。
    if args.enable_mocap:
        config.mocap.enabled = True
    elif args.disable_mocap:
        config.mocap.enabled = False

    mocap_csv = _resolve_root_path(args.csv_path, args.paths_config)
    if mocap_csv is not None:
        config.mocap.csv_path = mocap_csv
        config.mocap.enabled = True

    # 在真正打开 D455 前先做权重路径检查，失败时更快、更清楚。
    if config.yolo6d.model_path is None:
        raise ValueError("当前实时配置没有 model_path，请通过 YAML 或 --model 指定权重。")
    if not config.yolo6d.model_path.exists():
        raise FileNotFoundError(f"模型权重不存在: {config.yolo6d.model_path}")


def print_launch_summary(config: ProjectConfig, config_path: str | Path, max_frames: int | None) -> None:
    """把最终生效配置打印出来，方便现场确认本次运行到底用了什么。"""
    print("=== YOLO6D_Car 实机实时推理 ===")
    print(f"config      : {Path(config_path).resolve()}")
    print(f"model       : {config.yolo6d.model_path}")
    print(f"device      : {config.yolo6d.inference_device}")
    print(f"imgsz       : {config.yolo6d.inference_imgsz}")
    print(f"conf        : {config.yolo6d.conf_threshold}")
    print(f"camera      : {config.camera.source} {config.camera.color_width}x{config.camera.color_height}@{config.camera.fps}")
    print(f"depth       : {'on' if config.camera.enable_depth else 'off'}")
    print(f"window      : {'on' if config.output.show_window else 'off'}")
    print(f"json        : {'on' if config.output.print_json_lines else 'off'}")
    print(f"save_csv    : {config.output.save_csv if config.output.save_csv is not None else 'off'}")
    print(f"mocap       : {'on' if config.mocap.enabled else 'off'}")
    if config.mocap.enabled:
        print(f"mocap_csv   : {config.mocap.csv_path}")
    print(f"max_frames  : {max_frames if max_frames is not None else 'inf'}")
    print("按 Esc 可退出窗口。")


def main() -> None:
    """加载配置、应用覆盖参数，然后启动实时 pipeline。"""
    args = parse_args()
    if args.validate_config:
        validate_live_config(args)
        return None
    config = load_config(args.config, paths_config=args.paths_config)
    apply_overrides(config, args)
    print_launch_summary(config, args.config, args.max_frames)
    pipeline = PosePipeline(config)
    pipeline.run(max_frames=args.max_frames)


if __name__ == "__main__":
    main()
