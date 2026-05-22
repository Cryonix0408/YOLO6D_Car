"""将 Ultralytics Pose 结果导出为 JSON 回放格式。"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    """定义导出 replay JSON 所需的模型、样本目录和时间戳来源。"""
    parser = argparse.ArgumentParser(
        description="Run an Ultralytics pose model on a captured object session and export JSONReplay predictions."
    )
    parser.add_argument("--model", required=True, help="Path to a trained Ultralytics pose .pt model.")
    parser.add_argument("--samples-dir", required=True, help="Object capture session directory containing samples.csv.")
    parser.add_argument("--out", required=True, help="Output JSON replay path.")
    parser.add_argument("--label", default="car_model", help="Detection label written into replay JSON.")
    parser.add_argument("--conf-threshold", type=float, default=0.25, help="Detection confidence threshold.")
    parser.add_argument("--imgsz", type=int, default=640, help="Inference image size.")
    parser.add_argument("--device", default="", help="Inference device, for example 0, cpu, or empty for auto.")
    parser.add_argument(
        "--mocap-csv",
        default=None,
        help="Optional FzMotion CSV used to convert saved_local_time into the same relative seconds axis as the mocap provider.",
    )
    return parser.parse_args()


def _read_samples(samples_dir: Path) -> list[dict]:
    """读取采集 session 的 samples.csv，作为逐帧推理清单。"""
    samples_csv = samples_dir / "samples.csv"
    if not samples_csv.exists():
        raise FileNotFoundError(f"Missing samples.csv in {samples_dir}")

    rows: list[dict] = []
    with samples_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(row)
    if not rows:
        raise RuntimeError(f"No sample rows found in {samples_csv}")
    return rows


def _parse_fzmotion_start_time(text: str) -> datetime | None:
    """解析 FzMotion 元数据中的 StartTime，兼容带/不带毫秒两种格式。"""
    text = (text or "").strip()
    if not text:
        return None
    for fmt in ("%Y.%m.%d %H:%M:%S:%f", "%Y.%m.%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None


def _load_mocap_start_time(mocap_csv_path: Path | None) -> datetime | None:
    """从 FzMotion CSV 第一行元数据里读取动捕起始时间。"""
    if mocap_csv_path is None:
        return None
    if not mocap_csv_path.exists():
        raise FileNotFoundError(f"Mocap CSV not found: {mocap_csv_path}")

    with mocap_csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        first_row = next(reader, None)
    if not first_row:
        return None

    stripped = [cell.strip() for cell in first_row]
    for idx in range(0, len(stripped) - 1, 2):
        key = stripped[idx]
        value = stripped[idx + 1]
        if key == "StartTime":
            return _parse_fzmotion_start_time(value)
    return None


def _resolve_timestamp_s(row: dict[str, str], mocap_start_dt: datetime | None) -> tuple[float | None, str]:
    """把采集记录中的多种时间字段归一到 replay 使用的秒时间轴。"""
    saved_local_time = (row.get("saved_local_time") or "").strip()
    if saved_local_time and mocap_start_dt is not None:
        try:
            sample_dt = datetime.fromisoformat(saved_local_time)
            return (sample_dt - mocap_start_dt).total_seconds(), "saved_local_time"
        except ValueError:
            pass

    saved_unix = (row.get("saved_unix_time_s") or "").strip()
    if saved_unix and mocap_start_dt is not None:
        try:
            sample_dt = datetime.fromtimestamp(float(saved_unix))
            return (sample_dt - mocap_start_dt).total_seconds(), "saved_unix_time_s"
        except ValueError:
            pass

    if saved_unix:
        return float(saved_unix), "saved_unix_time_s"

    device_ts = (row.get("device_timestamp_s") or "").strip()
    if device_ts:
        return float(device_ts), "device_timestamp_s"

    return None, "missing"


def main() -> None:
    """对采集图片逐张跑 Ultralytics，并导出 JSONReplayBackend 可读格式。"""
    args = parse_args()
    samples_dir = Path(args.samples_dir).resolve()
    out_path = Path(args.out).resolve()
    mocap_csv_path = None if args.mocap_csv is None else Path(args.mocap_csv).resolve()
    mocap_start_dt = _load_mocap_start_time(mocap_csv_path)

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit(
            "Ultralytics is not installed in the current Python environment.\n"
            "Install it first, for example:\n"
            "  python -m pip install ultralytics\n"
        ) from exc

    model = YOLO(args.model)
    rows = _read_samples(samples_dir)

    frames: list[dict] = []
    timestamp_source_counter: dict[str, int] = {}
    for row in rows:
        # samples.csv 存的是相对图片路径；导出前先确认源图片仍存在。
        image_path = (samples_dir / row["image_path"]).resolve()
        if not image_path.exists():
            raise FileNotFoundError(f"Missing image referenced by samples.csv: {image_path}")

        results = model.predict(
            source=str(image_path),
            imgsz=args.imgsz,
            device=args.device,
            conf=args.conf_threshold,
            verbose=False,
        )
        result = results[0]

        detections: list[dict] = []
        boxes = getattr(result, "boxes", None)
        keypoints = getattr(result, "keypoints", None)
        if boxes is not None and keypoints is not None and len(boxes) > 0:
            # Ultralytics 的 keypoints 坐标已经是原图像素坐标，直接写入 replay。
            image_points = keypoints.xy.cpu().numpy()
            keypoint_scores = None
            if getattr(keypoints, "conf", None) is not None:
                keypoint_scores = keypoints.conf.cpu().numpy()

            boxes_conf = boxes.conf.cpu().numpy() if getattr(boxes, "conf", None) is not None else None
            count = min(len(image_points), len(boxes))
            for idx in range(count):
                confidence = 1.0 if boxes_conf is None else float(boxes_conf[idx])
                if confidence < args.conf_threshold:
                    continue

                detections.append(
                    {
                        "label": args.label,
                        "confidence": confidence,
                        "image_points_px": image_points[idx].tolist(),
                        "keypoint_scores": None if keypoint_scores is None else keypoint_scores[idx].tolist(),
                    }
                )

        timestamp_s, timestamp_source = _resolve_timestamp_s(row, mocap_start_dt)
        timestamp_source_counter[timestamp_source] = timestamp_source_counter.get(timestamp_source, 0) + 1

        frame_payload = {
            "frame_index": int(row["sample_index"]),
            "detections": detections,
        }
        if timestamp_s is not None:
            frame_payload["timestamp_s"] = float(timestamp_s)
        frames.append(frame_payload)

    payload = {"frames": frames}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "samples_dir": str(samples_dir),
        "model": args.model,
        "out": str(out_path),
        "mocap_csv": None if mocap_csv_path is None else str(mocap_csv_path),
        "mocap_start_time": None if mocap_start_dt is None else mocap_start_dt.isoformat(),
        "num_frames": len(frames),
        "num_frames_with_detections": sum(1 for frame in frames if frame["detections"]),
        "conf_threshold": args.conf_threshold,
        "timestamp_sources": timestamp_source_counter,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

