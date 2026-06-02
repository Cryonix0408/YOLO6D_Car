"""本文件作用：
    可视化并检查自动生成的 YOLO Pose 标签。

在 YOLO6D_Car pipeline 中的位置：
    labeling 后、dataset/training 前。它是防止错误标签进入训练集的人工检查入口。

主要输入：
    outputs/auto_labels/<session>/labels_yolo_pose/*.txt 和对应 images。

主要输出：
    overlay 图片、contact_sheet.png、label_stats.json、label_visualization_report.md。

注意事项：
    如果 2D keypoints/bbox 明显偏移、镜像或尺度不对，先检查内参、刚体名、时间同步，
    不要继续 prepare dataset 或训练。
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    import cv2
except ImportError as exc:
    raise RuntimeError("opencv-python is required for label visualization.") from exc

from yolo6d_car.path_utils import load_local_paths, resolve_path


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp"}
CUBOID_EDGES = (
    (0, 1),
    (1, 3),
    (3, 2),
    (2, 0),
    (4, 5),
    (5, 7),
    (7, 6),
    (6, 4),
    (0, 4),
    (1, 5),
    (2, 6),
    (3, 7),
)


@dataclass
class LabelRecord:
    """Parsed YOLO pose label for one image."""

    label_path: Path
    class_id: int
    bbox_xyxy: tuple[float, float, float, float]
    keypoints_xyv: np.ndarray
    raw_values: list[float]
    errors: list[str]


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Visualize YOLO6D auto labels over capture images.")
    parser.add_argument("--labels-root", required=True, help="Auto-label root, e.g. outputs/auto_labels/session.")
    parser.add_argument("--images-root", required=True, help="Capture image root for the same session.")
    parser.add_argument("--paths-config", default=None, help="Optional paths YAML, e.g. configs/paths_local.yaml.")
    parser.add_argument("--output-dir", required=True, help="Directory for overlays and reports.")
    parser.add_argument("--max-samples", type=int, default=100, help="Maximum matched labels to visualize.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for contact sheet sampling.")
    parser.add_argument("--contact-sheet-cols", type=int, default=5, help="Number of columns in the contact sheet.")
    parser.add_argument("--validate-config", action="store_true", help="Resolve paths and dependencies only.")
    return parser.parse_args()


def resolve_cli_path(raw_path: str, paths_config: str | None) -> Path:
    """Resolve a CLI path with the project's D/G-drive path rules."""
    local_paths = load_local_paths(paths_config) if paths_config else None
    path = resolve_path(raw_path, project_root=ROOT, local_paths=local_paths)
    if path is None:
        raise ValueError(f"Path is required: {raw_path}")
    return path.resolve()


def find_label_files(labels_root: Path) -> list[Path]:
    """Find YOLO pose txt labels under labels_yolo_pose/ or directly in labels_root."""
    label_dir = labels_root / "labels_yolo_pose"
    search_root = label_dir if label_dir.is_dir() else labels_root
    return sorted(path for path in search_root.glob("*.txt") if path.is_file())


def find_images(images_root: Path) -> dict[str, Path]:
    """Index image files by stem."""
    images = sorted(path for path in images_root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
    return {path.stem: path for path in images}


def load_annotations(labels_root: Path) -> dict[str, dict[str, Any]]:
    """Load optional annotations.jsonl records keyed by label and image stems."""
    path = labels_root / "annotations.jsonl"
    records: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                record = json.loads(text)
            except json.JSONDecodeError:
                records[f"__invalid_line_{line_number}"] = {"error": f"Invalid JSON on line {line_number}"}
                continue
            for key in ("label_path", "image_path"):
                value = record.get(key)
                if value:
                    records[Path(str(value)).stem] = record
    return records


def parse_label_file(label_path: Path, image_shape: tuple[int, int, int]) -> LabelRecord:
    """Parse one normalized YOLO pose label into pixel coordinates."""
    height, width = image_shape[:2]
    errors: list[str] = []
    text = label_path.read_text(encoding="utf-8").strip()
    if not text:
        return LabelRecord(label_path, -1, (math.nan, math.nan, math.nan, math.nan), np.empty((0, 3)), [], ["empty label"])

    first_line = text.splitlines()[0].strip()
    parts = first_line.split()
    try:
        values = [float(part) for part in parts]
    except ValueError:
        return LabelRecord(label_path, -1, (math.nan, math.nan, math.nan, math.nan), np.empty((0, 3)), [], ["non-numeric label"])

    if len(values) < 8:
        errors.append(f"too few values: {len(values)}")

    class_id = int(values[0]) if values and np.isfinite(values[0]) else -1
    if len(values) >= 5:
        cx, cy, box_w, box_h = values[1:5]
        bbox_xyxy = (
            (cx - box_w / 2.0) * width,
            (cy - box_h / 2.0) * height,
            (cx + box_w / 2.0) * width,
            (cy + box_h / 2.0) * height,
        )
    else:
        bbox_xyxy = (math.nan, math.nan, math.nan, math.nan)

    key_values = values[5:]
    if len(key_values) % 3 != 0:
        errors.append(f"keypoint value count is not divisible by 3: {len(key_values)}")
    count = len(key_values) // 3
    keypoints = np.zeros((count, 3), dtype=np.float64)
    for index in range(count):
        x_norm, y_norm, visibility = key_values[index * 3 : index * 3 + 3]
        keypoints[index] = [x_norm * width, y_norm * height, visibility]

    if count != 12:
        errors.append(f"expected 12 keypoints, found {count}")
    return LabelRecord(label_path, class_id, bbox_xyxy, keypoints, values, errors)


def bbox_is_reasonable(bbox: tuple[float, float, float, float], image_shape: tuple[int, int, int]) -> tuple[bool, str | None]:
    """Check whether a bbox is finite, positive, and overlaps the image."""
    height, width = image_shape[:2]
    x1, y1, x2, y2 = bbox
    if not np.all(np.isfinite([x1, y1, x2, y2])):
        return False, "bbox has NaN or Inf"
    if x2 <= x1 or y2 <= y1:
        return False, "bbox has non-positive size"
    area = (x2 - x1) * (y2 - y1)
    if area < 4.0:
        return False, "bbox is too small"
    if x2 < 0 or y2 < 0 or x1 >= width or y1 >= height:
        return False, "bbox is outside image"
    return True, None


def keypoint_checks(record: LabelRecord, image_shape: tuple[int, int, int]) -> dict[str, Any]:
    """Check NaN, bounds, and visibility for parsed keypoints."""
    height, width = image_shape[:2]
    keypoints = record.keypoints_xyv
    if keypoints.size == 0:
        return {
            "visible_count": 0,
            "nan_count": 0,
            "out_of_bounds_count": 0,
            "has_nan": False,
            "has_out_of_bounds": False,
        }

    finite_xy = np.isfinite(keypoints[:, :2]).all(axis=1)
    visible = keypoints[:, 2] > 0
    in_bounds = (
        finite_xy
        & (keypoints[:, 0] >= 0)
        & (keypoints[:, 0] < width)
        & (keypoints[:, 1] >= 0)
        & (keypoints[:, 1] < height)
    )
    nan_count = int((~finite_xy).sum())
    out_count = int((visible & ~in_bounds).sum())
    return {
        "visible_count": int(visible.sum()),
        "nan_count": nan_count,
        "out_of_bounds_count": out_count,
        "has_nan": nan_count > 0,
        "has_out_of_bounds": out_count > 0,
    }


def draw_label_overlay(image_bgr: np.ndarray, record: LabelRecord, annotation: dict[str, Any] | None) -> tuple[np.ndarray, dict[str, bool]]:
    """Draw 2D bbox, keypoints, optional projected 3D edges, and optional axes."""
    canvas = image_bgr.copy()
    draw_info = {"projected_3d_edges": False, "camera_axes": False}

    x1, y1, x2, y2 = record.bbox_xyxy
    if np.all(np.isfinite([x1, y1, x2, y2])):
        cv2.rectangle(canvas, (int(round(x1)), int(round(y1))), (int(round(x2)), int(round(y2))), (255, 170, 0), 2)

    for index, (x_coord, y_coord, visibility) in enumerate(record.keypoints_xyv):
        if not np.isfinite([x_coord, y_coord]).all():
            continue
        point = (int(round(x_coord)), int(round(y_coord)))
        if visibility >= 2:
            color = (40, 220, 40)
            radius = 4
        elif visibility > 0:
            color = (0, 220, 255)
            radius = 4
        else:
            color = (150, 150, 150)
            radius = 2
        cv2.circle(canvas, point, radius, color, -1)
        cv2.putText(canvas, str(index), (point[0] + 5, point[1] - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)

    projected = None
    if annotation:
        projected = annotation.get("projected_keypoints_px") or annotation.get("projected_corners_px")
    if isinstance(projected, list) and len(projected) >= 8:
        points = np.asarray(projected, dtype=np.float64)
        for start, end in CUBOID_EDGES:
            if start >= len(points) or end >= len(points):
                continue
            if not np.isfinite(points[[start, end], :2]).all():
                continue
            p1 = tuple(np.round(points[start, :2]).astype(int))
            p2 = tuple(np.round(points[end, :2]).astype(int))
            cv2.line(canvas, p1, p2, (255, 0, 255), 1, cv2.LINE_AA)
            draw_info["projected_3d_edges"] = True

    axis_points = annotation.get("axis_points_px") if annotation else None
    if isinstance(axis_points, list) and len(axis_points) >= 4:
        axis = np.asarray(axis_points[:4], dtype=np.float64)
        if np.isfinite(axis[:, :2]).all():
            origin = tuple(np.round(axis[0, :2]).astype(int))
            colors = ((0, 0, 255), (0, 255, 0), (255, 0, 0))
            for point, color in zip(axis[1:4], colors):
                endpoint = tuple(np.round(point[:2]).astype(int))
                cv2.arrowedLine(canvas, origin, endpoint, color, 2, tipLength=0.2)
            draw_info["camera_axes"] = True

    return canvas, draw_info


def create_contact_sheet(image_paths: list[Path], output_path: Path, cols: int = 5, thumb_size: tuple[int, int] = (220, 160)) -> bool:
    """Create a simple contact sheet from overlay images."""
    if not image_paths:
        return False
    thumbs: list[np.ndarray] = []
    for path in image_paths:
        image = cv2.imread(str(path))
        if image is None:
            continue
        thumb = cv2.resize(image, thumb_size)
        cv2.putText(thumb, path.stem, (6, thumb_size[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
        thumbs.append(thumb)
    if not thumbs:
        return False

    cols = max(1, cols)
    rows = int(math.ceil(len(thumbs) / cols))
    sheet = np.full((rows * thumb_size[1], cols * thumb_size[0], 3), 32, dtype=np.uint8)
    for index, thumb in enumerate(thumbs):
        row, col = divmod(index, cols)
        y1 = row * thumb_size[1]
        x1 = col * thumb_size[0]
        sheet[y1 : y1 + thumb_size[1], x1 : x1 + thumb_size[0]] = thumb
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return bool(cv2.imwrite(str(output_path), sheet))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_report(path: Path, stats: dict[str, Any]) -> None:
    """Write a Markdown quality report."""
    lines = [
        "# Auto Label Visualization Report",
        "",
        f"Result: **{stats['result']}**",
        "",
        "## Summary",
        "",
        f"- Labels found: {stats['labels_found']}",
        f"- Images found: {stats['images_found']}",
        f"- Matched label/image pairs: {stats['matched_pairs']}",
        f"- Overlays written: {stats['overlays_written']}",
        f"- Missing images for labels: {stats['missing_images_for_labels']}",
        f"- Images without labels: {stats['images_without_labels']}",
        f"- Invalid label files: {stats['invalid_label_files']}",
        f"- Files with NaN keypoints: {stats['files_with_nan_keypoints']}",
        f"- Files with out-of-bounds visible keypoints: {stats['files_with_out_of_bounds_keypoints']}",
        f"- Files with invalid bbox: {stats['files_with_invalid_bbox']}",
        f"- Mean visible keypoints: {stats['visible_keypoint_stats'].get('mean')}",
        "",
        "## Notes",
        "",
    ]
    for reason in stats["reasons"]:
        lines.append(f"- {reason}")
    if not stats["reasons"]:
        lines.append("- No blocking label-quality issues were detected in the sampled files.")
    lines.extend(
        [
            "",
            "## Optional Overlays",
            "",
            f"- Projected 3D bbox edges drawn: {stats['projected_3d_edge_overlays']}",
            f"- Camera axes drawn: {stats['camera_axis_overlays']}",
            "",
            "Camera axes are drawn only when labels provide pre-projected `axis_points_px`. A GT pose without intrinsics is reported but not reprojected here.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def summarize_numbers(values: list[float]) -> dict[str, float | None]:
    """Return simple finite-value stats."""
    arr = np.asarray([value for value in values if np.isfinite(value)], dtype=np.float64)
    if arr.size == 0:
        return {"min": None, "max": None, "mean": None, "median": None}
    return {
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
    }


def validate_config(args: argparse.Namespace) -> int:
    """Resolve paths and print a readiness payload without writing outputs."""
    labels_root = resolve_cli_path(args.labels_root, args.paths_config)
    images_root = resolve_cli_path(args.images_root, args.paths_config)
    output_dir = resolve_cli_path(args.output_dir, args.paths_config)
    payload = {
        "status": "ok",
        "labels_root": str(labels_root),
        "labels_root_exists": labels_root.exists(),
        "labels_yolo_pose_exists": (labels_root / "labels_yolo_pose").exists(),
        "annotations_jsonl_exists": (labels_root / "annotations.jsonl").exists(),
        "images_root": str(images_root),
        "images_root_exists": images_root.exists(),
        "output_dir": str(output_dir),
        "output_parent_exists": output_dir.parent.exists(),
        "opencv_import": "ok",
        "max_samples": args.max_samples,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def determine_result(stats: dict[str, Any]) -> tuple[str, list[str]]:
    """Classify visualization/check result as PASS, WARNING, or FAIL."""
    reasons: list[str] = []
    if stats["matched_pairs"] == 0:
        return "FAIL", ["no matched label/image pairs found"]
    if stats["invalid_label_files"] >= stats["matched_pairs"]:
        return "FAIL", ["all matched labels are invalid"]

    if stats["missing_images_for_labels"] > 0:
        reasons.append("some label files do not have matching images")
    if stats["images_without_labels"] > 0:
        reasons.append("some images do not have matching label files")
    if stats["invalid_label_files"] > 0:
        reasons.append("some label files could not be parsed cleanly")
    if stats["files_with_nan_keypoints"] > 0:
        reasons.append("some keypoints contain NaN or Inf")
    if stats["files_with_out_of_bounds_keypoints"] > 0:
        reasons.append("some visible keypoints are outside the image")
    if stats["files_with_invalid_bbox"] > 0:
        reasons.append("some bboxes are invalid or outside the image")
    if stats["keypoint_count_distribution"].get("12", 0) < stats["matched_pairs"]:
        reasons.append("not every matched label contains 12 keypoints")
    if reasons:
        return "WARNING", reasons
    return "PASS", []


def run_visualization(args: argparse.Namespace) -> int:
    """Run label checks, overlays, contact sheet, and reports."""
    labels_root = resolve_cli_path(args.labels_root, args.paths_config)
    images_root = resolve_cli_path(args.images_root, args.paths_config)
    output_dir = resolve_cli_path(args.output_dir, args.paths_config)

    if not labels_root.exists():
        raise FileNotFoundError(f"Labels root does not exist: {labels_root}")
    if not images_root.exists():
        raise FileNotFoundError(f"Images root does not exist: {images_root}")

    label_files = find_label_files(labels_root)
    image_by_stem = find_images(images_root)
    annotations = load_annotations(labels_root)

    matched = [(label, image_by_stem[label.stem]) for label in label_files if label.stem in image_by_stem]
    random.Random(args.seed).shuffle(matched)
    selected = matched[: max(0, args.max_samples)]

    overlays_dir = output_dir / "overlays"
    overlays_dir.mkdir(parents=True, exist_ok=True)

    visible_counts: list[float] = []
    overlay_paths: list[Path] = []
    keypoint_count_distribution: dict[str, int] = {}
    invalid_labels = 0
    nan_files = 0
    out_of_bounds_files = 0
    invalid_bbox_files = 0
    projected_edge_overlays = 0
    axis_overlays = 0
    per_file: list[dict[str, Any]] = []

    for label_path, image_path in selected:
        image = cv2.imread(str(image_path))
        if image is None:
            invalid_labels += 1
            per_file.append({"label": str(label_path), "image": str(image_path), "status": "image_unreadable"})
            continue

        record = parse_label_file(label_path, image.shape)
        checks = keypoint_checks(record, image.shape)
        bbox_ok, bbox_reason = bbox_is_reasonable(record.bbox_xyxy, image.shape)
        keypoint_count_distribution[str(record.keypoints_xyv.shape[0])] = keypoint_count_distribution.get(str(record.keypoints_xyv.shape[0]), 0) + 1

        if record.errors:
            invalid_labels += 1
        if checks["has_nan"]:
            nan_files += 1
        if checks["has_out_of_bounds"]:
            out_of_bounds_files += 1
        if not bbox_ok:
            invalid_bbox_files += 1

        visible_counts.append(float(checks["visible_count"]))
        annotation = annotations.get(label_path.stem) or annotations.get(image_path.stem)
        overlay, draw_info = draw_label_overlay(image, record, annotation)
        if draw_info["projected_3d_edges"]:
            projected_edge_overlays += 1
        if draw_info["camera_axes"]:
            axis_overlays += 1
        overlay_path = overlays_dir / f"{label_path.stem}_overlay.png"
        cv2.imwrite(str(overlay_path), overlay)
        overlay_paths.append(overlay_path)
        per_file.append(
            {
                "label": str(label_path),
                "image": str(image_path),
                "overlay": str(overlay_path),
                "keypoints": int(record.keypoints_xyv.shape[0]),
                "visible_keypoints": int(checks["visible_count"]),
                "nan_keypoints": int(checks["nan_count"]),
                "out_of_bounds_keypoints": int(checks["out_of_bounds_count"]),
                "bbox_ok": bool(bbox_ok),
                "bbox_reason": bbox_reason,
                "parse_errors": record.errors,
            }
        )

    contact_sheet_path = output_dir / "contact_sheet.png"
    create_contact_sheet(overlay_paths[: min(len(overlay_paths), 25)], contact_sheet_path, cols=args.contact_sheet_cols)

    stats: dict[str, Any] = {
        "labels_root": str(labels_root),
        "images_root": str(images_root),
        "output_dir": str(output_dir),
        "labels_found": len(label_files),
        "images_found": len(image_by_stem),
        "matched_pairs": len(matched),
        "sampled_pairs": len(selected),
        "overlays_written": len(overlay_paths),
        "missing_images_for_labels": len([label for label in label_files if label.stem not in image_by_stem]),
        "images_without_labels": len([stem for stem in image_by_stem if stem not in {label.stem for label in label_files}]),
        "invalid_label_files": invalid_labels,
        "files_with_nan_keypoints": nan_files,
        "files_with_out_of_bounds_keypoints": out_of_bounds_files,
        "files_with_invalid_bbox": invalid_bbox_files,
        "keypoint_count_distribution": keypoint_count_distribution,
        "visible_keypoint_stats": summarize_numbers(visible_counts),
        "projected_3d_edge_overlays": projected_edge_overlays,
        "camera_axis_overlays": axis_overlays,
        "contact_sheet": str(contact_sheet_path),
        "files": per_file,
    }
    result, reasons = determine_result(stats)
    stats["result"] = result
    stats["reasons"] = reasons

    write_json(output_dir / "label_stats.json", stats)
    write_report(output_dir / "label_visualization_report.md", stats)

    print(f"Label visualization result: {result}")
    print(f"Matched pairs: {stats['matched_pairs']}, overlays written: {stats['overlays_written']}")
    print(f"Report: {output_dir / 'label_visualization_report.md'}")
    return 0 if result in {"PASS", "WARNING"} else 2


def main() -> int:
    """Entry point."""
    args = parse_args()
    if args.validate_config:
        return validate_config(args)
    return run_visualization(args)


if __name__ == "__main__":
    raise SystemExit(main())
