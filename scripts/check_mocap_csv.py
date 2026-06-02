"""本文件作用：
    检查 FzMotion / Mocap CSV 是否适合用于自动标签和 GT 评估。

在 YOLO6D_Car pipeline 中的位置：
    mocap 数据进入 generate_mocap_labels.py 之前的质量门。

检查内容：
    文件大小、行数、时间戳范围、频率估计、NaN/空值、rigid body 名称、
    camera/object rigid 是否存在、有效帧数量、异常跳变。

注意事项：
    这里不修改原 CSV；如果格式不识别，会输出表头方便判断是否需要转换。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.path_utils import load_local_paths, resolve_path


@dataclass(slots=True)
class BodyStats:
    """Streaming stats for one rigid body."""

    count: int = 0
    timestamps: list[float] = field(default_factory=list)
    previous_timestamp: float | None = None
    previous_position: np.ndarray | None = None
    previous_quaternion: np.ndarray | None = None
    max_position_jump_m: float = 0.0
    max_rotation_jump_rad: float = 0.0
    position_jump_anomalies: int = 0
    rotation_jump_anomalies: int = 0
    positions_preview: list[list[float]] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    """Parse mocap quality CLI."""
    parser = argparse.ArgumentParser(description="Check FzMotion/mocap CSV quality before labeling.")
    parser.add_argument("--csv-path", required=True, help="Mocap CSV path, e.g. FZmotion_Data/raw_csv/session.csv.")
    parser.add_argument("--paths-config", default=None, help="Optional paths YAML, e.g. configs/paths_local.yaml.")
    parser.add_argument("--camera-rigid", required=True, help="Expected camera rigid body name.")
    parser.add_argument("--object-rigid", required=True, help="Expected object/car rigid body name.")
    parser.add_argument("--output-dir", required=True, help="Output directory for quality reports.")
    parser.add_argument("--plot", action="store_true", help="Generate PNG plots if matplotlib is available.")
    parser.add_argument("--validate-config", action="store_true", help="Resolve paths and imports without parsing the full CSV.")
    parser.add_argument("--position-jump-threshold-m", type=float, default=0.50, help="Adjacent-frame position jump threshold.")
    parser.add_argument("--rotation-jump-threshold-rad", type=float, default=1.50, help="Adjacent-frame rotation jump threshold.")
    parser.add_argument("--preview-max-points", type=int, default=5000, help="Max points retained per body for trajectory preview.")
    return parser.parse_args()


def resolve_cli_path(raw_path: str, paths_config: str | None) -> Path:
    """Resolve path through paths_local.yaml when provided."""
    local_paths = load_local_paths(paths_config) if paths_config else None
    path = resolve_path(raw_path, project_root=ROOT, local_paths=local_paths)
    if path is None:
        raise ValueError(f"Path is required: {raw_path}")
    return path.resolve()


def normalize_header(row: Iterable[str]) -> list[str]:
    """Strip CSV cells."""
    return [cell.strip() for cell in row]


def cell(row: list[str], index: int) -> str:
    """Return stripped cell text or empty."""
    return row[index].strip() if 0 <= index < len(row) else ""


def unit_scale_to_m(units: str) -> float:
    """Convert FzMotion length units to meters."""
    text = units.strip().lower()
    if text in {"m", "meter", "meters"}:
        return 1.0
    if text in {"cm", "centimeter", "centimeters"}:
        return 0.01
    if text in {"mm", "millimeter", "millimeters", ""}:
        return 0.001
    raise ValueError(f"Unsupported FzMotion LengthUnits: {units}")


def parse_float(text: str) -> float | None:
    """Parse finite float, returning None for empty/NaN/invalid."""
    if text is None or str(text).strip() == "":
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if not math.isfinite(value):
        return None
    return value


def quaternion_angle_delta(q1: np.ndarray, q2: np.ndarray) -> float:
    """Return angular distance between two xyzw quaternions."""
    q1 = np.asarray(q1, dtype=np.float64)
    q2 = np.asarray(q2, dtype=np.float64)
    n1 = np.linalg.norm(q1)
    n2 = np.linalg.norm(q2)
    if n1 <= 1e-12 or n2 <= 1e-12:
        return 0.0
    dot = abs(float(np.dot(q1 / n1, q2 / n2)))
    return float(2.0 * math.acos(max(-1.0, min(1.0, dot))))


def update_body(
    stats: dict[str, BodyStats],
    rigid_body: str,
    timestamp_s: float,
    position_m: np.ndarray,
    quaternion_xyzw: np.ndarray,
    *,
    position_jump_threshold_m: float,
    rotation_jump_threshold_rad: float,
    preview_max_points: int,
) -> None:
    """Update streaming stats for one valid body pose."""
    item = stats.setdefault(rigid_body, BodyStats())
    item.count += 1
    item.timestamps.append(timestamp_s)
    if item.previous_position is not None:
        position_jump = float(np.linalg.norm(position_m - item.previous_position))
        item.max_position_jump_m = max(item.max_position_jump_m, position_jump)
        if position_jump > position_jump_threshold_m:
            item.position_jump_anomalies += 1
    if item.previous_quaternion is not None:
        rotation_jump = quaternion_angle_delta(quaternion_xyzw, item.previous_quaternion)
        item.max_rotation_jump_rad = max(item.max_rotation_jump_rad, rotation_jump)
        if rotation_jump > rotation_jump_threshold_rad:
            item.rotation_jump_anomalies += 1
    item.previous_timestamp = timestamp_s
    item.previous_position = position_m.copy()
    item.previous_quaternion = quaternion_xyzw.copy()
    if len(item.positions_preview) < preview_max_points:
        item.positions_preview.append([timestamp_s, float(position_m[0]), float(position_m[1]), float(position_m[2])])


def detect_format_and_headers(csv_path: Path) -> tuple[str, list[str], list[list[str]]]:
    """Read the small header area and detect CSV format."""
    nonempty: list[list[str]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if any(cell.strip() for cell in row):
                nonempty.append(row)
            if len(nonempty) >= 6:
                break
    if not nonempty:
        raise ValueError(f"Mocap CSV is empty: {csv_path}")
    first = normalize_header(nonempty[0])
    if first and first[0] == "DataName":
        if len(nonempty) < 6:
            raise ValueError("FzMotion CSV header is incomplete; expected at least 6 non-empty header rows.")
        return "fzmotion_csv", first, nonempty
    return "generic_pose_csv", first, nonempty


def analyze_standard_csv(csv_path: Path, args: argparse.Namespace) -> tuple[dict[str, BodyStats], dict[str, Any]]:
    """Analyze generic timestamp/rigid_body/pose CSV."""
    required = {"timestamp", "rigid_body", "tx", "ty", "tz", "qx", "qy", "qz", "qw"}
    stats: dict[str, BodyStats] = {}
    empty_or_nan_cells = 0
    invalid_pose_rows = 0
    row_count = 0
    headers: list[str] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = list(reader.fieldnames or [])
        missing = sorted(required - set(headers))
        if missing:
            raise ValueError(f"Unrecognized mocap CSV format. Missing columns: {missing}. First columns: {headers[:12]}")
        for row in reader:
            row_count += 1
            values = [row.get(key, "") for key in required]
            empty_or_nan_cells += sum(1 for value in values if parse_float(value) is None and keyless_value_needs_float(value))
            rigid = str(row.get("rigid_body", "")).strip()
            timestamp = parse_float(str(row.get("timestamp", "")))
            tx, ty, tz = (parse_float(str(row.get(key, ""))) for key in ("tx", "ty", "tz"))
            qx, qy, qz, qw = (parse_float(str(row.get(key, ""))) for key in ("qx", "qy", "qz", "qw"))
            if not rigid or None in {timestamp, tx, ty, tz, qx, qy, qz, qw}:
                invalid_pose_rows += 1
                continue
            update_body(
                stats,
                rigid,
                float(timestamp),
                np.asarray([tx, ty, tz], dtype=np.float64),
                np.asarray([qx, qy, qz, qw], dtype=np.float64),
                position_jump_threshold_m=args.position_jump_threshold_m,
                rotation_jump_threshold_rad=args.rotation_jump_threshold_rad,
                preview_max_points=args.preview_max_points,
            )
    return stats, {
        "row_count": row_count,
        "headers": headers,
        "empty_or_nan_cells": empty_or_nan_cells,
        "invalid_pose_rows": invalid_pose_rows,
        "format_metadata": {},
    }


def keyless_value_needs_float(value: str) -> bool:
    """Return whether a value should count as empty/NaN for numeric fields."""
    return value is None or str(value).strip() == "" or str(value).strip().lower() in {"nan", "none", "null"}


def fzmotion_columns(header_rows: list[list[str]]) -> tuple[dict[str, dict[str, dict[str, int]]], dict[str, str], float]:
    """Extract FzMotion rigid-body columns and metadata."""
    metadata_row = normalize_header(header_rows[0])
    metadata: dict[str, str] = {}
    for index in range(0, len(metadata_row) - 1, 2):
        if metadata_row[index]:
            metadata[metadata_row[index]] = metadata_row[index + 1]
    scale = unit_scale_to_m(metadata.get("LengthUnits", "mm"))
    type_row = normalize_header(header_rows[1])
    name_row = normalize_header(header_rows[2])
    semantic_row = normalize_header(header_rows[4])
    axis_row = normalize_header(header_rows[5])
    max_columns = max(len(type_row), len(name_row), len(semantic_row), len(axis_row))
    columns: dict[str, dict[str, dict[str, int]]] = {}
    for idx in range(max_columns):
        if cell(type_row, idx) != "Rigid Body":
            continue
        name = cell(name_row, idx)
        semantic = cell(semantic_row, idx)
        axis = cell(axis_row, idx).upper()
        if not name or semantic not in {"Rotation", "Position"} or axis not in {"X", "Y", "Z", "W"}:
            continue
        columns.setdefault(name, {"Rotation": {}, "Position": {}})[semantic][axis] = idx
    return columns, metadata, scale


def analyze_fzmotion_csv(csv_path: Path, header_rows: list[list[str]], args: argparse.Namespace) -> tuple[dict[str, BodyStats], dict[str, Any]]:
    """Analyze FzMotion multi-row CSV without loading all data at once."""
    columns, metadata, scale = fzmotion_columns(header_rows)
    if not columns:
        headers = [normalize_header(row) for row in header_rows]
        raise ValueError(f"FzMotion CSV has no complete rigid-body columns. Header preview: {headers[:6]}")
    stats: dict[str, BodyStats] = {}
    empty_or_nan_cells = 0
    invalid_pose_rows = 0
    row_count = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        nonempty_seen = 0
        for row in reader:
            if not any(cell_text.strip() for cell_text in row):
                continue
            nonempty_seen += 1
            if nonempty_seen <= 6:
                continue
            row_count += 1
            timestamp = parse_float(cell(row, 1))
            if timestamp is None:
                invalid_pose_rows += 1
                empty_or_nan_cells += 1
                continue
            for rigid, body_columns in columns.items():
                rotation = body_columns["Rotation"]
                position = body_columns["Position"]
                if not {"X", "Y", "Z", "W"}.issubset(rotation) or not {"X", "Y", "Z"}.issubset(position):
                    continue
                raw_values = [
                    cell(row, position["X"]),
                    cell(row, position["Y"]),
                    cell(row, position["Z"]),
                    cell(row, rotation["X"]),
                    cell(row, rotation["Y"]),
                    cell(row, rotation["Z"]),
                    cell(row, rotation["W"]),
                ]
                parsed = [parse_float(value) for value in raw_values]
                empty_or_nan_cells += sum(1 for value in raw_values if keyless_value_needs_float(value))
                if any(value is None for value in parsed):
                    invalid_pose_rows += 1
                    continue
                tx, ty, tz, qx, qy, qz, qw = [float(value) for value in parsed]
                update_body(
                    stats,
                    rigid,
                    float(timestamp),
                    scale * np.asarray([tx, ty, tz], dtype=np.float64),
                    np.asarray([qx, qy, qz, qw], dtype=np.float64),
                    position_jump_threshold_m=args.position_jump_threshold_m,
                    rotation_jump_threshold_rad=args.rotation_jump_threshold_rad,
                    preview_max_points=args.preview_max_points,
                )
    return stats, {
        "row_count": row_count,
        "headers": normalize_header(header_rows[0]),
        "empty_or_nan_cells": empty_or_nan_cells,
        "invalid_pose_rows": invalid_pose_rows,
        "format_metadata": metadata,
    }


def summarize_timestamps(stats: dict[str, BodyStats]) -> dict[str, Any]:
    """Summarize timestamp range and frequency estimates."""
    all_ts = sorted(timestamp for body in stats.values() for timestamp in body.timestamps)
    unique_ts = sorted(set(all_ts))
    if not unique_ts:
        return {
            "timestamp_min_s": None,
            "timestamp_max_s": None,
            "duration_s": None,
            "estimated_frequency_hz": None,
        }
    dts = np.diff(np.asarray(unique_ts, dtype=np.float64))
    positive = dts[np.isfinite(dts) & (dts > 1e-9)]
    frequency = float(1.0 / np.median(positive)) if positive.size else None
    return {
        "timestamp_min_s": float(unique_ts[0]),
        "timestamp_max_s": float(unique_ts[-1]),
        "duration_s": float(unique_ts[-1] - unique_ts[0]),
        "estimated_frequency_hz": frequency,
        "unique_timestamp_count": len(unique_ts),
    }


def summarize_bodies(stats: dict[str, BodyStats]) -> dict[str, Any]:
    """Build per-rigid-body summary."""
    result: dict[str, Any] = {}
    for name, item in sorted(stats.items()):
        dts = np.diff(np.asarray(sorted(item.timestamps), dtype=np.float64))
        positive = dts[np.isfinite(dts) & (dts > 1e-9)]
        result[name] = {
            "valid_frames": item.count,
            "timestamp_min_s": float(min(item.timestamps)) if item.timestamps else None,
            "timestamp_max_s": float(max(item.timestamps)) if item.timestamps else None,
            "estimated_frequency_hz": float(1.0 / np.median(positive)) if positive.size else None,
            "max_position_jump_m": item.max_position_jump_m,
            "max_rotation_jump_rad": item.max_rotation_jump_rad,
            "position_jump_anomalies": item.position_jump_anomalies,
            "rotation_jump_anomalies": item.rotation_jump_anomalies,
        }
    return result


def analyze_csv(csv_path: Path, args: argparse.Namespace) -> dict[str, Any]:
    """Analyze CSV and return summary payload."""
    start = time.perf_counter()
    source_format, first_header, header_rows = detect_format_and_headers(csv_path)
    if source_format == "fzmotion_csv":
        stats, extra = analyze_fzmotion_csv(csv_path, header_rows, args)
    else:
        stats, extra = analyze_standard_csv(csv_path, args)
    elapsed = time.perf_counter() - start
    timestamp_summary = summarize_timestamps(stats)
    body_summary = summarize_bodies(stats)
    rigid_bodies = sorted(stats.keys())
    camera_exists = args.camera_rigid in stats
    object_exists = args.object_rigid in stats
    total_pose_records = sum(item.count for item in stats.values())
    anomaly_count = sum(item.position_jump_anomalies + item.rotation_jump_anomalies for item in stats.values())
    decision = "PASS"
    reasons: list[str] = []
    if not camera_exists:
        decision = "FAIL"
        reasons.append(f"camera_rigid missing: {args.camera_rigid}")
    if not object_exists:
        decision = "FAIL"
        reasons.append(f"object_rigid missing: {args.object_rigid}")
    if extra["invalid_pose_rows"] > 0 or extra["empty_or_nan_cells"] > 0:
        if decision != "FAIL":
            decision = "WARNING"
        reasons.append("NaN/empty/invalid values found")
    if anomaly_count > 0:
        if decision != "FAIL":
            decision = "WARNING"
        reasons.append("pose jump anomalies found")

    return {
        "csv_path": str(csv_path),
        "file_exists": csv_path.exists(),
        "file_size_bytes": csv_path.stat().st_size,
        "read_elapsed_s": elapsed,
        "source_format": source_format,
        "header_preview": first_header[:20],
        "row_count": extra["row_count"],
        "total_pose_records": total_pose_records,
        "rigid_bodies": rigid_bodies,
        "rigid_body_count": len(rigid_bodies),
        "camera_rigid": args.camera_rigid,
        "camera_rigid_exists": camera_exists,
        "object_rigid": args.object_rigid,
        "object_rigid_exists": object_exists,
        "empty_or_nan_cells": extra["empty_or_nan_cells"],
        "invalid_pose_rows": extra["invalid_pose_rows"],
        "timestamp_summary": timestamp_summary,
        "body_summary": body_summary,
        "format_metadata": extra["format_metadata"],
        "pose_jump_anomalies": anomaly_count,
        "decision": decision,
        "reasons": reasons,
        "_stats_for_plot": stats,
    }


def save_summary_csv(path: Path, summary: dict[str, Any]) -> None:
    """Save top-level scalar summary to CSV."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "value"])
        writer.writeheader()
        for key, value in summary.items():
            if key.startswith("_"):
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                writer.writerow({"metric": key, "value": value})
        for key, value in summary["timestamp_summary"].items():
            writer.writerow({"metric": f"timestamp_{key}", "value": value})


def save_report(path: Path, summary: dict[str, Any]) -> None:
    """Write markdown quality report."""
    lines = [
        "# Mocap CSV Quality Report",
        "",
        f"- CSV: `{summary['csv_path']}`",
        f"- Decision: **{summary['decision']}**",
        f"- Format: {summary['source_format']}",
        f"- File size: {summary['file_size_bytes']} bytes",
        f"- Read elapsed: {summary['read_elapsed_s']:.3f}s",
        f"- Row count: {summary['row_count']}",
        f"- Total pose records: {summary['total_pose_records']}",
        f"- Timestamp range: {summary['timestamp_summary']}",
        f"- Rigid bodies: {', '.join(summary['rigid_bodies'])}",
        f"- Camera rigid `{summary['camera_rigid']}` exists: {summary['camera_rigid_exists']}",
        f"- Object rigid `{summary['object_rigid']}` exists: {summary['object_rigid_exists']}",
        f"- Empty/NaN cells: {summary['empty_or_nan_cells']}",
        f"- Invalid pose rows: {summary['invalid_pose_rows']}",
        f"- Pose jump anomalies: {summary['pose_jump_anomalies']}",
        "",
        "## Reasons",
        "",
    ]
    if summary["reasons"]:
        lines.extend(f"- {reason}" for reason in summary["reasons"])
    else:
        lines.append("- No blocking issues detected.")
    lines.extend(["", "## Rigid Body Summary", ""])
    for name, body in summary["body_summary"].items():
        lines.append(f"- `{name}`: {body}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_rigid_body_list(path: Path, summary: dict[str, Any]) -> None:
    """Write rigid body names."""
    path.write_text("\n".join(summary["rigid_bodies"]) + "\n", encoding="utf-8")


def maybe_plot(output_dir: Path, summary: dict[str, Any]) -> list[str]:
    """Generate optional plots if matplotlib is available."""
    previous_mpl_config = None
    try:
        import os

        previous_mpl_config = os.environ.get("MPLCONFIGDIR")
        tmp_dir = tempfile.TemporaryDirectory(prefix="yolo6d_mpl_")
        os.environ["MPLCONFIGDIR"] = tmp_dir.name
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:
        return [f"Plotting skipped because matplotlib is unavailable: {exc}"]

    try:
        stats: dict[str, BodyStats] = summary["_stats_for_plot"]
        timestamps = sorted(set(timestamp for body in stats.values() for timestamp in body.timestamps))
        fig, ax = plt.subplots(figsize=(8, 4))
        if len(timestamps) >= 2:
            ax.hist(np.diff(np.asarray(timestamps)), bins=min(50, len(timestamps) - 1))
            ax.set_xlabel("dt (s)")
        else:
            ax.text(0.5, 0.5, "Not enough timestamps", ha="center")
        ax.set_title("Timestamp Distribution")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_dir / "timestamp_distribution.png", dpi=150)
        plt.close(fig)

        fig = plt.figure(figsize=(8, 6))
        ax3 = fig.add_subplot(111, projection="3d")
        plotted = False
        for name, body in stats.items():
            if not body.positions_preview:
                continue
            arr = np.asarray(body.positions_preview, dtype=np.float64)
            ax3.plot(arr[:, 1], arr[:, 2], arr[:, 3], label=name)
            plotted = True
        if plotted:
            ax3.legend()
            ax3.set_xlabel("x (m)")
            ax3.set_ylabel("y (m)")
            ax3.set_zlabel("z (m)")
        else:
            ax3.text2D(0.5, 0.5, "No trajectory", transform=ax3.transAxes, ha="center")
        ax3.set_title("Position Trajectory Preview")
        fig.tight_layout()
        fig.savefig(output_dir / "position_trajectory_preview.png", dpi=150)
        plt.close(fig)
        return []
    finally:
        tmp_dir.cleanup()
        import os

        if previous_mpl_config is None:
            os.environ.pop("MPLCONFIGDIR", None)
        else:
            os.environ["MPLCONFIGDIR"] = previous_mpl_config


def public_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Remove non-serial/report internals."""
    return {key: value for key, value in summary.items() if not key.startswith("_")}


def main() -> None:
    """Run mocap CSV quality check."""
    args = parse_args()
    csv_path = resolve_cli_path(args.csv_path, args.paths_config)
    output_dir = resolve_cli_path(args.output_dir, args.paths_config)

    if args.validate_config:
        payload = {
            "status": "ok",
            "csv_path": str(csv_path),
            "csv_exists": csv_path.exists(),
            "output_dir": str(output_dir),
            "output_parent_exists": output_dir.parent.exists(),
            "camera_rigid": args.camera_rigid,
            "object_rigid": args.object_rigid,
            "plot": bool(args.plot),
        }
        if csv_path.exists():
            try:
                fmt, header, _ = detect_format_and_headers(csv_path)
                payload.update({"source_format": fmt, "header_preview": header[:20]})
            except Exception as exc:
                payload.update({"source_format": "unrecognized", "error": str(exc)})
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return None

    if not csv_path.exists():
        raise FileNotFoundError(f"Mocap CSV not found: {csv_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        summary = analyze_csv(csv_path, args)
    except Exception as exc:
        fmt = "unknown"
        header_preview: list[str] = []
        try:
            fmt, header_preview, _ = detect_format_and_headers(csv_path)
        except Exception:
            pass
        error_payload = {
            "csv_path": str(csv_path),
            "decision": "FAIL",
            "source_format": fmt,
            "header_preview": header_preview[:20],
            "error": str(exc),
        }
        (output_dir / "mocap_summary.json").write_text(json.dumps(error_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        raise

    plot_warnings = maybe_plot(output_dir, summary) if args.plot else []
    clean = public_summary(summary)
    clean["plot_warnings"] = plot_warnings
    (output_dir / "mocap_summary.json").write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    save_summary_csv(output_dir / "mocap_summary.csv", clean)
    save_report(output_dir / "mocap_quality_report.md", clean)
    save_rigid_body_list(output_dir / "rigid_body_list.txt", clean)
    print(
        json.dumps(
            {
                "status": "ok",
                "decision": clean["decision"],
                "output_dir": str(output_dir),
                "rigid_bodies": clean["rigid_bodies"],
                "reasons": clean["reasons"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
