"""海康工业相机实时预览测试脚本。"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.camera.hikvision_camera import HikvisionCamera


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test Hikvision industrial camera preview.")
    parser.add_argument("--device-index", type=int, default=0, help="相机索引，默认第 0 台。")
    parser.add_argument("--exposure-time-us", type=float, default=None, help="曝光时间，单位微秒。")
    parser.add_argument(
        "--exposure-auto",
        default="continuous",
        help="自动曝光模式：continuous / once / off。默认 continuous。",
    )
    parser.add_argument("--auto-exposure-upper-us", type=float, default=None, help="自动曝光上限，单位微秒。")
    parser.add_argument("--gain-db", type=float, default=None, help="增益，单位 dB。")
    parser.add_argument(
        "--gain-auto",
        default="continuous",
        help="自动增益模式：continuous / once / off。默认 continuous。",
    )
    parser.add_argument("--auto-gain-upper-db", type=float, default=None, help="自动增益上限，单位 dB。")
    parser.add_argument("--frame-rate", type=float, default=None, help="帧率。")
    parser.add_argument("--gamma", type=float, default=None, help="相机侧 Gamma，范围通常为 0.1-4.0。")
    parser.add_argument("--preview-gamma", type=float, default=None, help="仅预览用 Gamma，不改变相机输出。")
    parser.add_argument("--preview-gain", type=float, default=1.0, help="仅预览用亮度倍率，不改变相机输出。")
    parser.add_argument("--pixel-format", default="auto", help="像素格式，例如 auto / RGB8Packed / Mono8。")
    parser.add_argument("--grab-timeout-ms", type=int, default=1000, help="取流超时时间，单位毫秒。")
    parser.add_argument("--mvs-python-path", default=None, help="MvCameraControl_class.py 所在目录。")
    return parser.parse_args()


def main() -> None:
    log("解析启动参数")
    args = parse_args()
    pixel_format = None if str(args.pixel_format).lower() == "auto" else args.pixel_format
    exposure_auto = None if args.exposure_time_us is not None else args.exposure_auto
    gain_auto = None if args.gain_db is not None else args.gain_auto
    log(f"MVS Python path: {args.mvs_python_path or '<auto>'}")
    log(f"device_index={args.device_index}, pixel_format={pixel_format or 'auto'}")

    log("创建 HikvisionCamera 对象")
    camera = HikvisionCamera(
        device_index=args.device_index,
        exposure_time_us=args.exposure_time_us,
        exposure_auto=exposure_auto,
        auto_exposure_upper_us=args.auto_exposure_upper_us,
        gain_db=args.gain_db,
        gain_auto=gain_auto,
        auto_gain_upper_db=args.auto_gain_upper_db,
        frame_rate=args.frame_rate,
        gamma=args.gamma,
        pixel_format=pixel_format,
        grab_timeout_ms=args.grab_timeout_ms,
        mvs_python_path=args.mvs_python_path,
    )

    log("打开相机：加载 SDK、枚举设备、创建句柄")
    camera.open()
    log("相机已打开，准备开始取流")
    camera.start()
    log("海康相机已启动，按 q 退出")
    last_tick = time.perf_counter()
    fps = 0.0

    try:
        while True:
            frame_id, timestamp, image = camera.get_frame()
            now = time.perf_counter()
            delta_t = max(now - last_tick, 1e-6)
            inst_fps = 1.0 / delta_t
            fps = inst_fps if fps <= 0.0 else fps * 0.9 + inst_fps * 0.1
            last_tick = now
            preview = apply_preview_adjustment(image, args.preview_gain, args.preview_gamma)
            preview_mean = float(np.mean(preview))
            cv2.putText(
                preview,
                f"frame={frame_id} ts={timestamp:.6f}",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                preview,
                (
                    f"pixel={camera.last_pixel_type_name} "
                    f"raw_mean={camera.last_mean_intensity:.1f} display_mean={preview_mean:.1f}"
                ),
                (20, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                preview,
                (
                    f"exp_auto={camera.last_exposure_auto} exp={camera.last_exposure_time_us:.1f}us "
                    f"gain_auto={camera.last_gain_auto} gain={camera.last_gain_db:.1f}dB"
                ),
                (20, 105),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.60,
                (0, 200, 255),
                2,
                cv2.LINE_AA,
            )
            frame_rate_enable_text = (
                "on" if camera.last_acquisition_frame_rate_enable is True
                else "off" if camera.last_acquisition_frame_rate_enable is False
                else "unknown"
            )
            cv2.putText(
                preview,
                (
                    f"preview_fps={fps:.1f} "
                    f"cam_rate_enable={frame_rate_enable_text} "
                    f"cam_rate={camera.last_acquisition_frame_rate_fps:.1f}fps"
                ),
                (20, 140),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.60,
                (255, 220, 0),
                2,
                cv2.LINE_AA,
            )
            cv2.imshow("Hikvision Camera Test", preview)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
    finally:
        camera.stop()
        camera.close()
        cv2.destroyAllWindows()


def apply_preview_adjustment(image: np.ndarray, preview_gain: float, preview_gamma: float | None) -> np.ndarray:
    """只增强窗口显示，不改相机真实输出，方便在暗场景下观察构图。"""
    preview = image
    if abs(float(preview_gain) - 1.0) > 1e-6:
        preview = cv2.convertScaleAbs(preview, alpha=float(preview_gain), beta=0.0)
    else:
        preview = preview.copy()

    if preview_gamma is not None and abs(float(preview_gamma) - 1.0) > 1e-6:
        gamma = max(float(preview_gamma), 1e-3)
        inv_gamma = 1.0 / gamma
        table = np.array([(i / 255.0) ** inv_gamma * 255.0 for i in range(256)], dtype=np.uint8)
        preview = cv2.LUT(preview, table)
    return preview


def log(message: str) -> None:
    """打印实时进度，避免打开相机时终端看起来没有响应。"""
    print(f"[test_hikvision_camera] {message}", flush=True)


if __name__ == "__main__":
    main()
