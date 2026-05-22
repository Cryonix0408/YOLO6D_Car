"""手动采集小车图像、深度和时间戳。"""

from __future__ import annotations

import json
import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

# 小车采集和标定板采集共用 D455 打开、保存图像、写 samples.csv 的逻辑。
from capture_board_samples import (  # noqa: E402
    D455Stream,
    ImageFrame,
    _draw_overlay,
    _ensure_dirs,
    _next_sample_index,
    _open_manifest,
    _save_frame,
    _save_intrinsics,
    _save_session_info,
    cv2,
    load_config,
)


def parse_args() -> argparse.Namespace:
    """定义小车采集参数；多数目录和相机设置来自 YAML。"""
    parser = argparse.ArgumentParser(description="Capture car/object samples from a D455 camera.")
    parser.add_argument("--config", required=True, help="Path to the project YAML config.")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to store captured samples. Defaults to outputs/object_capture/<timestamp>.",
    )
    parser.add_argument(
        "--prefix",
        default="car",
        help="Filename prefix for saved samples.",
    )
    parser.add_argument(
        "--save-depth",
        action="store_true",
        help="Save aligned depth PNG files in addition to color images.",
    )
    parser.add_argument(
        "--warmup-frames",
        type=int,
        default=20,
        help="Number of initial frames to discard before sampling.",
    )
    return parser.parse_args()


def _default_output_dir() -> Path:
    """默认用时间戳创建一个不会互相覆盖的 object_capture session。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return ROOT / "outputs" / "object_capture" / timestamp


def main() -> None:
    """启动 D455 预览，按空格保存小车样本，按 Esc/q 退出。"""
    args = parse_args()

    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    output_dir = Path(args.output_dir).resolve() if args.output_dir else _default_output_dir()

    images_dir, depth_dir = _ensure_dirs(output_dir, save_depth=args.save_depth)
    manifest_writer, manifest_handle = _open_manifest(output_dir)

    stream = D455Stream(config.camera)
    stream.start()

    try:
        # 丢弃前几帧，让自动曝光和 RealSense pipeline 稳定下来。
        for _ in range(max(args.warmup_frames, 0)):
            stream.wait_for_frame()

        frame = stream.wait_for_frame()
        _save_intrinsics(output_dir, frame.intrinsics)
        _save_session_info(output_dir, config_path=config_path, save_depth=args.save_depth)

        sample_index = _next_sample_index(images_dir=images_dir, prefix=args.prefix)
        saved_count = sample_index

        while True:
            # 预览帧使用 copy，避免在保存原始图像前把 HUD 画进数据。
            frame = stream.wait_for_frame()
            preview = ImageFrame(
                color=frame.color.copy(),
                depth=frame.depth,
                timestamp_s=frame.timestamp_s,
                intrinsics=frame.intrinsics,
            )
            _draw_overlay(preview, sample_count=saved_count, output_dir=output_dir)
            cv2.imshow("D455 Object Capture", preview.color)

            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q"), ord("Q")):
                break

            if key == ord(" "):
                # 每次按空格保存 color/depth，并在 manifest 中写入时间戳。
                image_path, depth_path = _save_frame(
                    frame=frame,
                    sample_index=sample_index,
                    prefix=args.prefix,
                    images_dir=images_dir,
                    depth_dir=depth_dir,
                    manifest=manifest_writer,
                )
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
        manifest_handle.close()
        stream.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()



