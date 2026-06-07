"""Collect a fixed-rate image sequence from a Hikvision MVS camera.

This script only captures and saves frames. It does not run YOLO, PnP, or
tracking, so it can be used as a clean data-recording tool for fast-motion data.
"""

from __future__ import annotations

import argparse
import csv
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.camera.hikvision_camera import HikvisionCamera


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect continuous frames from a Hikvision camera."
    )
    parser.add_argument("--output-dir", required=True, help="Output directory.")
    parser.add_argument("--duration", type=float, required=True, help="Capture duration in seconds.")
    parser.add_argument("--fps", type=float, required=True, help="Target capture FPS.")
    parser.add_argument("--exposure-us", type=float, default=None, help="Manual exposure time in us.")
    parser.add_argument("--gain", type=float, default=None, help="Manual gain in dB.")
    parser.add_argument("--width", type=int, default=None, help="Camera image width.")
    parser.add_argument("--height", type=int, default=None, help="Camera image height.")
    parser.add_argument("--device-index", type=int, default=0, help="Hikvision device index.")
    parser.add_argument(
        "--pixel-format",
        default="auto",
        help="Pixel format. Use auto, RGB8Packed, BGR8Packed, Mono8, or an SDK enum name.",
    )
    parser.add_argument(
        "--mvs-python-path",
        default=None,
        help="Directory containing MvCameraControl_class.py.",
    )
    parser.add_argument(
        "--png-compression",
        type=int,
        default=1,
        help="PNG compression level, 0-9. Lower is faster. Default: 1.",
    )
    parser.add_argument(
        "--write-queue-size",
        type=int,
        default=512,
        help="Maximum pending image writes before capture blocks.",
    )
    parser.add_argument("--preview", action="store_true", help="Show a live preview while collecting.")
    parser.add_argument("--preview-every", type=int, default=1, help="Preview every Nth captured frame.")
    parser.add_argument("--preview-scale", type=float, default=0.6, help="Preview display scale.")
    parser.add_argument("--preview-max-width", type=int, default=1280, help="Maximum preview window image width.")
    parser.add_argument("--preview-max-height", type=int, default=720, help="Maximum preview window image height.")
    parser.add_argument("--preview-gain", type=float, default=1.0, help="Display-only brightness multiplier.")
    parser.add_argument("--preview-gamma", type=float, default=1.0, help="Display-only gamma. Larger values brighten preview.")
    parser.add_argument(
        "--preview-before-start",
        action="store_true",
        help="Show live preview first. Press s to start saving frames, or q/ESC to quit.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    validate_args(args)

    output_dir = Path(args.output_dir).resolve()
    images_dir = output_dir / "images"
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    config_path = output_dir / "config.yaml"
    timestamps_path = output_dir / "camera_timestamps.csv"
    target_frames = int(round(args.duration * args.fps))
    period_s = 1.0 / float(args.fps)
    pixel_format = None if str(args.pixel_format).lower() == "auto" else args.pixel_format

    config: dict[str, Any] = {
        "script": "scripts/collect_hikvision_sequence.py",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "output_dir": str(output_dir),
        "images_dir": str(images_dir),
        "camera_timestamps_csv": str(timestamps_path),
        "camera": {
            "backend": "hikvision_mvs",
            "device_index": args.device_index,
            "mvs_python_path": args.mvs_python_path,
            "width": args.width,
            "height": args.height,
            "fps": args.fps,
            "exposure_time_us": args.exposure_us,
            "gain_db": args.gain,
            "pixel_format": pixel_format or "auto",
        },
        "capture": {
            "duration_s": args.duration,
            "target_fps": args.fps,
            "target_frames": target_frames,
            "png_compression": args.png_compression,
            "timestamp_source": "HikvisionCamera.get_frame timestamp",
            "note": "Timestamp comes from camera backend when available, otherwise host perf_counter.",
        },
        "preview": {
            "enabled": args.preview,
            "preview_every": args.preview_every,
            "preview_scale": args.preview_scale,
            "preview_max_width": args.preview_max_width,
            "preview_max_height": args.preview_max_height,
            "preview_gain": args.preview_gain,
            "preview_gamma": args.preview_gamma,
            "preview_before_start": args.preview_before_start,
            "note": "Preview enhancement is display-only. Saved images remain raw camera frames.",
        },
    }
    write_yaml(config_path, config)

    camera = HikvisionCamera(
        device_index=args.device_index,
        exposure_time_us=args.exposure_us,
        exposure_auto=None if args.exposure_us is not None else "continuous",
        gain_db=args.gain,
        gain_auto=None if args.gain is not None else "continuous",
        frame_rate=args.fps,
        width=args.width,
        height=args.height,
        pixel_format=pixel_format,
        mvs_python_path=args.mvs_python_path,
    )

    write_queue: queue.Queue[tuple[Path, Any] | None] = queue.Queue(
        maxsize=args.write_queue_size
    )
    writer_errors: list[str] = []
    writer = threading.Thread(
        target=image_writer_worker,
        args=(write_queue, int(args.png_compression), writer_errors),
        daemon=True,
    )

    captured = 0
    start_perf = 0.0
    end_perf = 0.0
    preview_window = "Hikvision Capture Preview - q quit"
    preview_started = False

    print("[collect] opening camera", flush=True)
    camera.open()

    try:
        writer.start()
        print("[collect] starting camera stream", flush=True)
        camera.start()

        start_perf = time.perf_counter()
        next_capture_perf = start_perf
        preview_enabled = args.preview or args.preview_before_start
        if preview_enabled:
            cv2.namedWindow(preview_window, cv2.WINDOW_NORMAL)
            preview_started = True
        if args.preview_before_start:
            should_start = run_preview_before_start(
                camera=camera,
                window_name=preview_window,
                preview_gain=args.preview_gain,
                preview_gamma=args.preview_gamma,
                preview_scale=args.preview_scale,
                max_width=args.preview_max_width,
                max_height=args.preview_max_height,
            )
            if not should_start:
                print("[collect] preview quit requested before capture", flush=True)
                end_perf = time.perf_counter()
                return
            print("[collect] capture started by key s", flush=True)
            start_perf = time.perf_counter()
            next_capture_perf = start_perf
        elif args.preview:
            print("[collect] live preview enabled, press q or ESC to stop early", flush=True)

        with timestamps_path.open("w", newline="", encoding="utf-8") as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow([
                "frame_id",
                "timestamp",
                "host_perf_counter_s",
                "saved_unix_time_s",
                "saved_local_time",
                "image_path",
            ])

            while captured < target_frames:
                sleep_s = next_capture_perf - time.perf_counter()
                if sleep_s > 0:
                    time.sleep(min(sleep_s, period_s))

                frame_id, timestamp, image = camera.get_frame()
                host_perf_counter_s = time.perf_counter()
                saved_unix_time_s = time.time()
                saved_local_time = datetime.now().isoformat(timespec="milliseconds")
                captured += 1
                image_path = images_dir / f"{captured:06d}.png"

                csv_writer.writerow([
                    frame_id,
                    f"{float(timestamp):.9f}",
                    f"{host_perf_counter_s:.9f}",
                    f"{saved_unix_time_s:.6f}",
                    saved_local_time,
                    str(image_path),
                ])
                write_queue.put((image_path, image))

                next_capture_perf += period_s
                elapsed = time.perf_counter() - start_perf
                actual_fps = captured / max(elapsed, 1e-9)

                if args.preview and captured % args.preview_every == 0:
                    preview = make_preview_image(
                        image,
                        preview_gain=args.preview_gain,
                        preview_gamma=args.preview_gamma,
                        preview_scale=args.preview_scale,
                        max_width=args.preview_max_width,
                        max_height=args.preview_max_height,
                    )
                    draw_preview_overlay(
                        preview,
                        captured=captured,
                        target_frames=target_frames,
                        frame_id=frame_id,
                        timestamp=timestamp,
                        actual_fps=actual_fps,
                        queue_size=write_queue.qsize(),
                    )
                    cv2.imshow(preview_window, preview)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (ord("q"), 27):
                        print("[collect] preview quit requested, saving partial sequence", flush=True)
                        break

                if captured == 1 or captured % max(int(args.fps), 1) == 0:
                    print(
                        f"[collect] captured={captured}/{target_frames} "
                        f"actual_fps={actual_fps:.2f}",
                        flush=True,
                    )

        end_perf = time.perf_counter()
    except KeyboardInterrupt:
        end_perf = time.perf_counter()
        print("[collect] interrupted by Ctrl+C, saving partial sequence", flush=True)
    finally:
        print("[collect] stopping camera and waiting for image writer", flush=True)
        try:
            camera.stop()
        finally:
            camera.close()

        write_queue.put(None)
        write_queue.join()
        writer.join(timeout=10.0)
        if preview_started:
            cv2.destroyWindow(preview_window)

    elapsed_s = max(end_perf - start_perf, 0.0) if start_perf > 0.0 else 0.0
    config["capture"].update(
        {
            "saved_frames": captured,
            "elapsed_s": elapsed_s,
            "actual_fps": captured / elapsed_s if elapsed_s > 0 else 0.0,
            "writer_errors": writer_errors,
        }
    )
    write_yaml(config_path, config)

    if writer_errors:
        raise RuntimeError(f"Image writer failed {len(writer_errors)} time(s): {writer_errors[0]}")

    print(
        f"[collect] done saved_frames={captured} "
        f"actual_fps={config['capture']['actual_fps']:.2f} "
        f"output_dir={output_dir}",
        flush=True,
    )


def validate_args(args: argparse.Namespace) -> None:
    if args.duration <= 0:
        raise ValueError("--duration must be greater than 0")
    if args.fps <= 0:
        raise ValueError("--fps must be greater than 0")
    if args.width is not None and args.width <= 0:
        raise ValueError("--width must be greater than 0")
    if args.height is not None and args.height <= 0:
        raise ValueError("--height must be greater than 0")
    if not 0 <= args.png_compression <= 9:
        raise ValueError("--png-compression must be in [0, 9]")
    if args.write_queue_size <= 0:
        raise ValueError("--write-queue-size must be greater than 0")
    if args.preview_every <= 0:
        raise ValueError("--preview-every must be greater than 0")
    if args.preview_scale <= 0:
        raise ValueError("--preview-scale must be greater than 0")
    if args.preview_max_width <= 0:
        raise ValueError("--preview-max-width must be greater than 0")
    if args.preview_max_height <= 0:
        raise ValueError("--preview-max-height must be greater than 0")
    if args.preview_gain <= 0:
        raise ValueError("--preview-gain must be greater than 0")
    if args.preview_gamma <= 0:
        raise ValueError("--preview-gamma must be greater than 0")


def run_preview_before_start(
    camera: HikvisionCamera,
    window_name: str,
    preview_gain: float,
    preview_gamma: float,
    preview_scale: float,
    max_width: int,
    max_height: int,
) -> bool:
    print("[collect] preview-before-start: press s to start capture, q/ESC to quit", flush=True)
    last_tick = time.perf_counter()
    fps = 0.0

    while True:
        frame_id, timestamp, image = camera.get_frame()
        now = time.perf_counter()
        inst_fps = 1.0 / max(now - last_tick, 1e-6)
        fps = inst_fps if fps <= 0.0 else fps * 0.9 + inst_fps * 0.1
        last_tick = now

        preview = make_preview_image(
            image,
            preview_gain=preview_gain,
            preview_gamma=preview_gamma,
            preview_scale=preview_scale,
            max_width=max_width,
            max_height=max_height,
        )
        draw_waiting_preview_overlay(preview, frame_id=frame_id, timestamp=timestamp, fps=fps)
        cv2.imshow(window_name, preview)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("s"):
            return True
        if key in (ord("q"), 27):
            return False


def make_preview_image(    image: np.ndarray,
    preview_gain: float,
    preview_gamma: float,
    preview_scale: float,
    max_width: int,
    max_height: int,
) -> np.ndarray:
    frame = image
    if abs(preview_gain - 1.0) > 1e-6:
        frame = np.clip(frame.astype(np.float32) * float(preview_gain), 0, 255).astype(np.uint8)
    if abs(preview_gamma - 1.0) > 1e-6:
        inv_gamma = 1.0 / float(preview_gamma)
        lut = ((np.arange(256, dtype=np.float32) / 255.0) ** inv_gamma * 255.0).clip(0, 255).astype(np.uint8)
        frame = cv2.LUT(frame, lut)
    return resize_preview(frame, preview_scale, max_width, max_height)


def resize_preview(
    image: np.ndarray,
    preview_scale: float,
    max_width: int,
    max_height: int,
) -> np.ndarray:
    height, width = image.shape[:2]
    scale = min(float(preview_scale), max_width / float(width), max_height / float(height))
    if scale >= 0.999:
        return image.copy()
    new_size = (max(int(width * scale), 1), max(int(height * scale), 1))
    return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)


def draw_preview_overlay(
    image: np.ndarray,
    captured: int,
    target_frames: int,
    frame_id: int,
    timestamp: float,
    actual_fps: float,
    queue_size: int,
) -> None:
    mean_value = float(np.mean(image))
    lines = [
        f"saved={captured}/{target_frames} sdk_frame={frame_id}",
        f"ts={timestamp:.6f} fps={actual_fps:.1f} write_q={queue_size}",
        f"preview_mean={mean_value:.1f} q/ESC=stop",
    ]
    x, y = 18, 34
    for line in lines:
        cv2.putText(image, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 0), 5, cv2.LINE_AA)
        cv2.putText(image, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 255, 0), 2, cv2.LINE_AA)
        y += 34

def draw_waiting_preview_overlay(
    image: np.ndarray,
    frame_id: int,
    timestamp: float,
    fps: float,
) -> None:
    mean_value = float(np.mean(image))
    lines = [
        "PREVIEW ONLY - not saving",
        f"frame={frame_id} ts={timestamp:.6f} fps={fps:.1f} mean={mean_value:.1f}",
        "press s=start capture, q/ESC=quit",
    ]
    x, y = 18, 34
    for line in lines:
        cv2.putText(image, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 0), 5, cv2.LINE_AA)
        cv2.putText(image, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 255, 255), 2, cv2.LINE_AA)
        y += 34


def image_writer_worker(    write_queue: queue.Queue[tuple[Path, Any] | None],
    png_compression: int,
    errors: list[str],
) -> None:
    while True:
        item = write_queue.get()
        try:
            if item is None:
                return
            image_path, image = item
            ok = cv2.imwrite(
                str(image_path),
                image,
                [cv2.IMWRITE_PNG_COMPRESSION, int(png_compression)],
            )
            if not ok:
                errors.append(f"Failed to write image: {image_path}")
        except Exception as exc:
            errors.append(str(exc))
        finally:
            write_queue.task_done()


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(format_yaml(payload), encoding="utf-8")


def format_yaml(value: Any, indent: int = 0) -> str:
    space = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{space}{key}:")
                lines.append(format_yaml(item, indent + 2).rstrip())
            else:
                lines.append(f"{space}{key}: {format_yaml_scalar(item)}")
        return "\n".join(lines) + "\n"
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{space}-")
                lines.append(format_yaml(item, indent + 2).rstrip())
            else:
                lines.append(f"{space}- {format_yaml_scalar(item)}")
        return "\n".join(lines) + "\n"
    return f"{space}{format_yaml_scalar(value)}\n"


def format_yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


if __name__ == "__main__":
    main()

