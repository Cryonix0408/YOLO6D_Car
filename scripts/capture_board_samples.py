"""手动采集标定板图像、深度和时间戳。"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# 项目根目录：当前脚本文件往上两级
ROOT = Path(__file__).resolve().parents[1]

# 项目源码目录 src
SRC = ROOT / "src"

# 把 src 加入 Python 搜索路径，方便导入自定义模块
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# 导入 OpenCV，如果没安装则报错
try:
    import cv2
except ImportError as exc:
    raise RuntimeError("opencv-python is required to run the capture preview.") from exc

# 项目中的自定义模块
from yolo6d_car.camera.d455 import D455Stream
from yolo6d_car.config import load_config
from yolo6d_car.path_utils import load_local_paths
from yolo6d_car.types import CameraIntrinsics, ImageFrame


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="Capture calibration board samples from a D455 camera.")

    # 必填：配置文件路径
    parser.add_argument("--config", required=True, help="Path to the project YAML config.")
    parser.add_argument("--paths-config", default=None, help="Optional local paths YAML, e.g. configs/paths_local.yaml.")
    parser.add_argument("--validate-config", action="store_true", help="Validate config and paths without opening the camera.")

    # 输出目录，可不填；不填则自动生成 outputs/board_capture/时间戳
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to store captured samples. Defaults to outputs/board_capture/<timestamp>.",
    )

    # 保存文件前缀，默认是 board
    parser.add_argument(
        "--prefix",
        default="board",
        help="Filename prefix for saved samples.",
    )

    # 是否同时保存对齐后的深度图
    parser.add_argument(
        "--save-depth",
        action="store_true",
        help="Save aligned depth PNG files in addition to color images.",
    )

    # 预热帧数：开始采样前先丢弃若干帧
    parser.add_argument(
        "--warmup-frames",
        type=int,
        default=20,
        help="Number of initial frames to discard before sampling.",
    )
    return parser.parse_args()


def validate_capture_config(args: argparse.Namespace) -> None:
    """Validate capture config without opening D455 or creating data files."""
    config_path = Path(args.config).resolve()
    config = load_config(config_path, paths_config=args.paths_config)
    output_dir = Path(args.output_dir).resolve() if args.output_dir else _default_output_dir(args.paths_config)
    payload = {
        "status": "ok",
        "script": Path(__file__).name,
        "config": str(config_path),
        "paths_config": None if args.paths_config is None else str(Path(args.paths_config).resolve()),
        "camera": {
            "source": config.camera.source,
            "width": config.camera.color_width,
            "height": config.camera.color_height,
            "fps": config.camera.fps,
            "enable_depth": config.camera.enable_depth,
        },
        "output_dir": str(output_dir),
        "output_parent_exists": output_dir.parent.exists(),
        "opencv_available": cv2 is not None,
        "hardware_required": False,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _default_output_dir(paths_config: str | None = None) -> Path:
    """生成默认输出目录 outputs/board_capture/时间戳"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if paths_config:
        return load_local_paths(paths_config).outputs_root / "board_capture" / timestamp
    return ROOT / "outputs" / "board_capture" / timestamp


def _ensure_dirs(output_dir: Path, save_depth: bool) -> tuple[Path, Path | None]:
    """创建输出目录、images目录，以及可选的depth目录"""
    output_dir.mkdir(parents=True, exist_ok=True)

    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    depth_dir = None
    if save_depth:
        depth_dir = output_dir / "depth"
        depth_dir.mkdir(parents=True, exist_ok=True)

    return images_dir, depth_dir


def _save_intrinsics(output_dir: Path, intrinsics: CameraIntrinsics) -> None:
    """保存相机内参到 intrinsics.json"""
    payload = {
        "fx": intrinsics.fx,
        "fy": intrinsics.fy,
        "cx": intrinsics.cx,
        "cy": intrinsics.cy,
        "width": intrinsics.width,
        "height": intrinsics.height,
        "dist_coeffs": intrinsics.dist_coeffs.tolist(),
    }
    with (output_dir / "intrinsics.json").open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _save_session_info(output_dir: Path, config_path: Path, save_depth: bool) -> None:
    """保存本次采集会话信息到 session.json"""
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),  # 创建时间
        "config_path": str(config_path),  # 使用的配置文件路径
        "save_depth": save_depth,  # 是否保存深度图
    }
    with (output_dir / "session.json").open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _next_sample_index(images_dir: Path, prefix: str) -> int:
    """扫描已有图片，计算下一张图片编号"""
    existing = sorted(images_dir.glob(f"{prefix}_*.png"))
    if not existing:
        return 0

    max_index = -1
    for path in existing:
        stem = path.stem
        try:
            # 从文件名里取出最后的编号，例如 board_0003 -> 3
            max_index = max(max_index, int(stem.rsplit("_", 1)[1]))
        except (IndexError, ValueError):
            continue

    return max_index + 1


def _open_manifest(output_dir: Path) -> tuple[csv.DictWriter, object]:
    """打开或创建 samples.csv，用来记录保存样本的信息"""
    manifest_path = output_dir / "samples.csv"
    file_exists = manifest_path.exists()

    handle = manifest_path.open("a", encoding="utf-8", newline="")
    writer = csv.DictWriter(
        handle,
        fieldnames=[
            "sample_index",  # 样本编号
            "image_path",  # 彩色图路径
            "depth_path",  # 深度图路径
            "device_timestamp_s",  # 相机设备时间戳
            "saved_unix_time_s",  # 保存时的Unix时间戳
            "saved_local_time",  # 本地可读时间
        ],
    )

    # 如果是新文件，先写表头
    if not file_exists:
        writer.writeheader()

    return writer, handle


def _draw_overlay(frame: ImageFrame, sample_count: int, output_dir: Path) -> None:
    """在预览图像上绘制提示信息"""
    lines = [
        "Space: save current frame",
        "Q / Esc: quit",
        f"saved: {sample_count}",
        f"timestamp: {frame.timestamp_s:.3f}s",
        f"output: {output_dir}",
    ]

    y = 30
    for line in lines:
        cv2.putText(
            frame.color,
            line,
            (16, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
        y += 28


def _save_frame(
        frame: ImageFrame,
        sample_index: int,
        prefix: str,
        images_dir: Path,
        depth_dir: Path | None,
        manifest: csv.DictWriter,
) -> tuple[Path, Path | None]:
    """保存当前帧的彩色图、可选深度图，并写入CSV记录"""

    # 生成文件名，例如 board_0000
    file_stem = f"{prefix}_{sample_index:04d}"

    # 保存彩色图
    image_path = images_dir / f"{file_stem}.png"
    if not cv2.imwrite(str(image_path), frame.color):
        raise RuntimeError(f"Failed to save color image: {image_path}")

    # 如果需要并且当前帧有深度图，则保存深度图
    depth_path = None
    if depth_dir is not None and frame.depth is not None:
        depth_path = depth_dir / f"{file_stem}.png"
        if not cv2.imwrite(str(depth_path), frame.depth):
            raise RuntimeError(f"Failed to save depth image: {depth_path}")

    # 将本次保存的信息追加到 CSV
    manifest.writerow(
        {
            "sample_index": sample_index,
            "image_path": image_path.relative_to(images_dir.parent).as_posix(),
            "depth_path": "" if depth_path is None else depth_path.relative_to(images_dir.parent).as_posix(),
            "device_timestamp_s": f"{frame.timestamp_s:.6f}",
            "saved_unix_time_s": f"{time.time():.6f}",
            "saved_local_time": datetime.now().isoformat(timespec="milliseconds"),
        }
    )

    return image_path, depth_path


def main() -> None:
    """主函数：打开相机、预览图像、按空格保存"""
    args = parse_args()
    if args.validate_config:
        validate_capture_config(args)
        return None

    # 解析配置文件路径并加载配置
    config_path = Path(args.config).resolve()
    config = load_config(config_path, paths_config=args.paths_config)

    # 确定输出目录
    output_dir = Path(args.output_dir).resolve() if args.output_dir else _default_output_dir(args.paths_config)

    # 创建目录
    images_dir, depth_dir = _ensure_dirs(output_dir, save_depth=args.save_depth)

    # 打开样本记录 CSV
    manifest_writer, manifest_handle = _open_manifest(output_dir)

    # 打开 D455 数据流
    stream = D455Stream(config.camera)
    stream.start()

    try:
        # 预热：先丢弃若干帧，防止初始帧不稳定
        for _ in range(max(args.warmup_frames, 0)):
            stream.wait_for_frame()

        # 先取一帧，用于保存内参与会话信息
        frame = stream.wait_for_frame()
        _save_intrinsics(output_dir, frame.intrinsics)
        _save_session_info(output_dir, config_path=config_path, save_depth=args.save_depth)

        # 计算下一个样本编号
        sample_index = _next_sample_index(images_dir=images_dir, prefix=args.prefix)
        saved_count = sample_index

        # 主循环：显示实时画面
        while True:
            frame = stream.wait_for_frame()

            # 复制一份彩色图，仅用于预览叠加文字，不影响原始保存图像
            preview = ImageFrame(
                color=frame.color.copy(),
                depth=frame.depth,
                timestamp_s=frame.timestamp_s,
                intrinsics=frame.intrinsics,
            )

            # 绘制提示信息
            _draw_overlay(preview, sample_count=saved_count, output_dir=output_dir)

            # 显示窗口
            cv2.imshow("D455 Board Capture", preview.color)

            # 读取键盘输入
            key = cv2.waitKey(1) & 0xFF

            # Esc / q / Q 退出
            if key in (27, ord("q"), ord("Q")):
                break

            # 空格键保存当前帧
            if key == ord(" "):
                image_path, depth_path = _save_frame(
                    frame=frame,
                    sample_index=sample_index,
                    prefix=args.prefix,
                    images_dir=images_dir,
                    depth_dir=depth_dir,
                    manifest=manifest_writer,
                )

                # 在控制台打印一条 JSON 记录，方便外部程序读取
                print(
                    json.dumps(
                        {
                            "sample_index": sample_index,
                            "image_path": str(image_path),
                            "depth_path": None if depth_path is None else str(depth_path),
                            "device_timestamp_s": frame.timestamp_s,
                        },
                        ensure_ascii=False,
                    )
                )

                sample_index += 1
                saved_count += 1

    finally:
        # 无论如何都要释放资源
        manifest_handle.close()
        stream.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
