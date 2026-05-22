"""Preview and summarize a Hikvision image sequence.

Input is the output directory produced by scripts/collect_hikvision_sequence.py.
The script can play frames, save a sampled contact sheet, and save a preview
video. It intentionally does not run YOLO.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize a collected Hikvision sequence.")
    parser.add_argument("--sequence-dir", required=True, help="Directory that contains images/ and camera_timestamps.csv.")
    parser.add_argument("--play", action="store_true", help="Play the sequence in an OpenCV window.")
    parser.add_argument("--save-grid", action="store_true", help="Save an evenly sampled contact sheet.")
    parser.add_argument("--save-video", action="store_true", help="Save a preview mp4 video.")
    parser.add_argument("--grid-count", type=int, default=36, help="Number of frames in the contact sheet.")
    parser.add_argument("--video-fps", type=float, default=None, help="Preview video FPS. Default: estimated capture FPS.")
    parser.add_argument("--display-scale", type=float, default=0.6, help="Scale used for playback display.")
    parser.add_argument("--max-width", type=int, default=1280, help="Maximum playback/video frame width.")
    parser.add_argument("--max-height", type=int, default=720, help="Maximum playback/video frame height.")
    parser.add_argument("--start-index", type=int, default=0, help="Start at this zero-based frame index.")
    parser.add_argument("--stride", type=int, default=1, help="Play/export every Nth frame.")
    parser.add_argument("--no-overlay", action="store_true", help="Do not draw frame/timestamp overlays.")
    parser.add_argument("--grid-path", default=None, help="Optional output path for the contact sheet.")
    parser.add_argument("--video-path", default=None, help="Optional output path for the preview video.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    validate_args(args)

    sequence_dir = Path(args.sequence_dir).resolve()
    images_dir = sequence_dir / "images"
    timestamps_path = sequence_dir / "camera_timestamps.csv"

    rows = load_timestamp_rows(timestamps_path)
    if rows:
        entries = rows
    else:
        entries = [{"frame_id": str(i + 1), "timestamp": "", "image_path": str(path)} for i, path in enumerate(sorted(images_dir.glob("*.png")))]

    if not entries:
        raise RuntimeError(f"No frames found in {images_dir}")

    entries = entries[args.start_index :: args.stride]
    stats = compute_sequence_stats(entries)
    print_sequence_summary(sequence_dir, entries, stats)

    grid_path = Path(args.grid_path).resolve() if args.grid_path else sequence_dir / "preview_grid.jpg"
    video_path = Path(args.video_path).resolve() if args.video_path else sequence_dir / "preview.mp4"

    if args.save_grid:
        save_contact_sheet(entries, sequence_dir, grid_path, args.grid_count, draw_overlay=not args.no_overlay)
        print(f"[visualize] grid saved: {grid_path}", flush=True)

    if args.save_video:
        fps = args.video_fps or stats.get("estimated_fps") or 30.0
        save_preview_video(
            entries,
            sequence_dir,
            video_path,
            fps=float(fps),
            max_width=args.max_width,
            max_height=args.max_height,
            draw_overlay=not args.no_overlay,
        )
        print(f"[visualize] video saved: {video_path}", flush=True)

    if args.play or (not args.save_grid and not args.save_video):
        play_sequence(
            entries,
            sequence_dir,
            display_scale=args.display_scale,
            max_width=args.max_width,
            max_height=args.max_height,
            draw_overlay=not args.no_overlay,
        )


def validate_args(args: argparse.Namespace) -> None:
    if args.grid_count <= 0:
        raise ValueError("--grid-count must be greater than 0")
    if args.display_scale <= 0:
        raise ValueError("--display-scale must be greater than 0")
    if args.stride <= 0:
        raise ValueError("--stride must be greater than 0")
    if args.start_index < 0:
        raise ValueError("--start-index must be non-negative")
    if args.video_fps is not None and args.video_fps <= 0:
        raise ValueError("--video-fps must be greater than 0")


def load_timestamp_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not row.get("image_path"):
                continue
            rows.append(
                {
                    "frame_id": str(row.get("frame_id", "")),
                    "timestamp": str(row.get("timestamp", "")),
                    "image_path": str(row.get("image_path", "")),
                }
            )
    return rows


def compute_sequence_stats(entries: list[dict[str, str]]) -> dict[str, Any]:
    timestamps = []
    for entry in entries:
        try:
            timestamps.append(float(entry.get("timestamp", "")))
        except ValueError:
            pass

    stats: dict[str, Any] = {"num_frames": len(entries)}
    if len(timestamps) >= 2:
        deltas = np.diff(np.asarray(timestamps, dtype=np.float64))
        valid = deltas[deltas > 0]
        if valid.size:
            stats.update(
                {
                    "duration_s": float(timestamps[-1] - timestamps[0]),
                    "mean_dt_s": float(np.mean(valid)),
                    "median_dt_s": float(np.median(valid)),
                    "min_dt_s": float(np.min(valid)),
                    "max_dt_s": float(np.max(valid)),
                    "estimated_fps": float(1.0 / np.mean(valid)),
                }
            )
    return stats


def print_sequence_summary(sequence_dir: Path, entries: list[dict[str, str]], stats: dict[str, Any]) -> None:
    print(f"[visualize] sequence_dir={sequence_dir}", flush=True)
    print(f"[visualize] frames={stats['num_frames']}", flush=True)
    if "estimated_fps" in stats:
        print(
            "[visualize] "
            f"estimated_fps={stats['estimated_fps']:.2f} "
            f"duration={stats['duration_s']:.3f}s "
            f"dt_mean={stats['mean_dt_s'] * 1000.0:.2f}ms "
            f"dt_min={stats['min_dt_s'] * 1000.0:.2f}ms "
            f"dt_max={stats['max_dt_s'] * 1000.0:.2f}ms",
            flush=True,
        )

    first_image = resolve_image_path(entries[0]["image_path"], sequence_dir)
    image = cv2.imread(str(first_image), cv2.IMREAD_COLOR)
    if image is not None:
        print(f"[visualize] image_shape={image.shape[1]}x{image.shape[0]}", flush=True)


def play_sequence(
    entries: list[dict[str, str]],
    sequence_dir: Path,
    display_scale: float,
    max_width: int,
    max_height: int,
    draw_overlay: bool,
) -> None:
    paused = False
    index = 0
    window_name = "Hikvision Sequence - q quit, space pause, a/d step"
    print("[visualize] controls: q=quit, space=pause, a=prev, d=next", flush=True)

    while 0 <= index < len(entries):
        entry = entries[index]
        image = cv2.imread(str(resolve_image_path(entry["image_path"], sequence_dir)), cv2.IMREAD_COLOR)
        if image is None:
            print(f"[visualize] missing image: {entry['image_path']}", flush=True)
            index += 1
            continue

        frame = image.copy()
        if draw_overlay:
            draw_frame_overlay(frame, entry, index, len(entries))
        frame = resize_for_display(frame, display_scale, max_width, max_height)

        cv2.imshow(window_name, frame)
        delay_ms = 0 if paused else 1
        key = cv2.waitKey(delay_ms) & 0xFF
        if key == ord("q") or key == 27:
            break
        if key == ord(" "):
            paused = not paused
            continue
        if key == ord("a"):
            index = max(index - 1, 0)
            paused = True
            continue
        if key == ord("d"):
            index = min(index + 1, len(entries) - 1)
            paused = True
            continue
        if not paused:
            index += 1

    cv2.destroyWindow(window_name)


def save_contact_sheet(
    entries: list[dict[str, str]],
    sequence_dir: Path,
    output_path: Path,
    grid_count: int,
    draw_overlay: bool,
) -> None:
    indices = evenly_spaced_indices(len(entries), min(grid_count, len(entries)))
    thumbs = []
    thumb_w, thumb_h = 320, 180

    for idx in indices:
        entry = entries[idx]
        image = cv2.imread(str(resolve_image_path(entry["image_path"], sequence_dir)), cv2.IMREAD_COLOR)
        if image is None:
            continue
        if draw_overlay:
            draw_frame_overlay(image, entry, idx, len(entries))
        thumbs.append(cv2.resize(image, (thumb_w, thumb_h), interpolation=cv2.INTER_AREA))

    if not thumbs:
        raise RuntimeError("No readable frames for contact sheet")

    cols = int(math.ceil(math.sqrt(len(thumbs))))
    rows = int(math.ceil(len(thumbs) / cols))
    sheet = np.full((rows * thumb_h, cols * thumb_w, 3), 24, dtype=np.uint8)

    for i, thumb in enumerate(thumbs):
        y = (i // cols) * thumb_h
        x = (i % cols) * thumb_w
        sheet[y : y + thumb_h, x : x + thumb_w] = thumb

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 92]):
        raise RuntimeError(f"Failed to write contact sheet: {output_path}")


def save_preview_video(
    entries: list[dict[str, str]],
    sequence_dir: Path,
    output_path: Path,
    fps: float,
    max_width: int,
    max_height: int,
    draw_overlay: bool,
) -> None:
    first = cv2.imread(str(resolve_image_path(entries[0]["image_path"], sequence_dir)), cv2.IMREAD_COLOR)
    if first is None:
        raise RuntimeError(f"Failed to read first image: {entries[0]['image_path']}")

    first = resize_to_fit(first, max_width, max_height)
    height, width = first.shape[:2]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Failed to open video writer: {output_path}")

    try:
        for idx, entry in enumerate(entries):
            image = cv2.imread(str(resolve_image_path(entry["image_path"], sequence_dir)), cv2.IMREAD_COLOR)
            if image is None:
                continue
            if draw_overlay:
                draw_frame_overlay(image, entry, idx, len(entries))
            writer.write(resize_to_fit(image, max_width, max_height))
    finally:
        writer.release()


def draw_frame_overlay(image: np.ndarray, entry: dict[str, str], index: int, total: int) -> None:
    mean_value = float(np.mean(image))
    lines = [
        f"idx={index + 1}/{total} frame_id={entry.get('frame_id', '')}",
        f"timestamp={entry.get('timestamp', '')}",
        f"mean={mean_value:.1f} path={Path(entry.get('image_path', '')).name}",
    ]
    x, y = 18, 34
    for line in lines:
        cv2.putText(image, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 0), 5, cv2.LINE_AA)
        cv2.putText(image, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 255, 255), 2, cv2.LINE_AA)
        y += 34


def resize_for_display(image: np.ndarray, scale: float, max_width: int, max_height: int) -> np.ndarray:
    scaled_w = max(int(image.shape[1] * scale), 1)
    scaled_h = max(int(image.shape[0] * scale), 1)
    return resize_to_fit(image, min(scaled_w, max_width), min(scaled_h, max_height))


def resize_to_fit(image: np.ndarray, max_width: int, max_height: int) -> np.ndarray:
    h, w = image.shape[:2]
    scale = min(max_width / float(w), max_height / float(h), 1.0)
    if scale >= 1.0:
        return image
    new_size = (max(int(w * scale), 1), max(int(h * scale), 1))
    return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)


def evenly_spaced_indices(length: int, count: int) -> list[int]:
    if count <= 1:
        return [0]
    return [int(round(i * (length - 1) / float(count - 1))) for i in range(count)]


def resolve_image_path(path_text: str, sequence_dir: Path) -> Path:
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (sequence_dir / path).resolve()


if __name__ == "__main__":
    main()
