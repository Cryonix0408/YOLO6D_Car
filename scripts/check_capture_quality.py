"""本文件作用：
    检查一个 capture session 是否适合进入自动标签和训练。

在 YOLO6D_Car pipeline 中的位置：
    capture 后、labeling 前。它不修改采集数据，只生成质量报告。

检查内容：
    图片数量、分辨率一致性、损坏图片、blur_score、frame_difference_score、
    metadata 完整性、重复/过于相似图片、最低样本数。

结果解释：
    PASS 可继续；WARNING 需要人工看报告；FAIL 应先修复或重采。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
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
    raise RuntimeError("opencv-python is required for capture quality checks.") from exc

from yolo6d_car.path_utils import load_local_paths, resolve_path


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp"}


def parse_args() -> argparse.Namespace:
    """Parse quality-check arguments."""
    parser = argparse.ArgumentParser(description="Check an object capture session for labeling/training readiness.")
    parser.add_argument("--capture-root", required=True, help="Capture session root, e.g. captures/date/session.")
    parser.add_argument("--paths-config", default=None, help="Optional paths YAML, e.g. configs/paths_local.yaml.")
    parser.add_argument("--output-dir", required=True, help="Directory for quality reports.")
    parser.add_argument("--plot", action="store_true", help="Generate PNG plots if matplotlib is available.")
    parser.add_argument("--validate-config", action="store_true", help="Resolve paths and imports without scanning images.")
    parser.add_argument("--min-samples", type=int, default=30, help="Minimum acceptable image count.")
    parser.add_argument("--blur-threshold", type=float, default=80.0, help="Images below this blur score are considered blurry.")
    parser.add_argument("--max-blurry-fraction", type=float, default=0.25, help="Fail if blurry fraction exceeds this value.")
    parser.add_argument("--duplicate-scene-threshold", type=float, default=0.01, help="Adjacent scene-change score below this is too similar.")
    parser.add_argument("--max-duplicate-fraction", type=float, default=0.20, help="Warn/fail if duplicate fraction is too high.")
    return parser.parse_args()


def resolve_cli_path(raw_path: str, paths_config: str | None) -> Path:
    """Resolve a CLI path with D/G-drive path rules."""
    local_paths = load_local_paths(paths_config) if paths_config else None
    path = resolve_path(raw_path, project_root=ROOT, local_paths=local_paths)
    if path is None:
        raise ValueError(f"Path is required: {raw_path}")
    return path.resolve()


def find_images(capture_root: Path) -> list[Path]:
    """Find capture images under images/ first, then fall back to root recursion."""
    images_dir = capture_root / "images"
    search_root = images_dir if images_dir.is_dir() else capture_root
    images = [path for path in search_root.rglob("*") if path.suffix.lower() in IMAGE_EXTENSIONS and path.is_file()]
    return sorted(images)


def read_capture_index(capture_root: Path) -> tuple[list[dict[str, str]], list[str]]:
    """Read capture_index.csv if present."""
    path = capture_root / "capture_index.csv"
    if not path.exists():
        return [], ["capture_index.csv missing"]
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        headers = list(reader.fieldnames or [])
    required = {"sample_id", "timestamp", "image_path", "blur_score", "frame_difference_score", "scene_change_score"}
    missing = sorted(required - set(headers))
    warnings = [f"capture_index.csv missing columns: {missing}"] if missing else []
    return rows, warnings


def load_json(path: Path) -> dict[str, Any] | None:
    """Load JSON with None on failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def blur_score(image_bgr: np.ndarray) -> float:
    """Compute Laplacian variance blur score."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def gray_float(image_bgr: np.ndarray, size: tuple[int, int] | None = None) -> np.ndarray:
    """Return grayscale float image, optionally resized."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    if size is not None:
        gray = cv2.resize(gray, size)
    return gray.astype(np.float32)


def scene_change(current_gray: np.ndarray, previous_gray: np.ndarray | None) -> tuple[float, float]:
    """Compute mean absolute difference and normalized scene change."""
    if previous_gray is None:
        return 0.0, 0.0
    if current_gray.shape != previous_gray.shape:
        previous_gray = cv2.resize(previous_gray, (current_gray.shape[1], current_gray.shape[0]))
    diff = float(np.mean(np.abs(current_gray - previous_gray)))
    return diff, diff / 255.0


def finite_stats(values: list[float]) -> dict[str, float | None]:
    """Return simple stats over finite values."""
    arr = np.asarray([value for value in values if np.isfinite(value)], dtype=np.float64)
    if arr.size == 0:
        return {"min": None, "max": None, "mean": None, "median": None, "p10": None, "p90": None}
    return {
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "p10": float(np.percentile(arr, 10)),
        "p90": float(np.percentile(arr, 90)),
    }


def analyze_images(capture_root: Path, images: list[Path], duplicate_threshold: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read images and compute per-image quality metrics."""
    rows: list[dict[str, Any]] = []
    previous_gray = None
    resolution_counts: dict[str, int] = {}
    damaged = 0
    duplicates = 0

    for index, image_path in enumerate(images, start=1):
        rel = image_path.relative_to(capture_root).as_posix() if image_path.is_relative_to(capture_root) else image_path.name
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            damaged += 1
            rows.append(
                {
                    "sample_index": index,
                    "image_path": rel,
                    "readable": False,
                    "width": "",
                    "height": "",
                    "blur_score": "",
                    "frame_difference_score": "",
                    "scene_change_score": "",
                    "too_similar_to_previous": "",
                }
            )
            continue

        height, width = image.shape[:2]
        resolution_key = f"{width}x{height}"
        resolution_counts[resolution_key] = resolution_counts.get(resolution_key, 0) + 1
        gray = gray_float(image)
        diff, change = scene_change(gray, previous_gray)
        too_similar = index > 1 and change < duplicate_threshold
        if too_similar:
            duplicates += 1
        score = blur_score(image)
        rows.append(
            {
                "sample_index": index,
                "image_path": rel,
                "readable": True,
                "width": width,
                "height": height,
                "blur_score": score,
                "frame_difference_score": diff,
                "scene_change_score": change,
                "too_similar_to_previous": too_similar,
            }
        )
        previous_gray = gray

    summary = {
        "damaged_images": damaged,
        "resolution_counts": resolution_counts,
        "resolution_mismatch": len(resolution_counts) > 1,
        "duplicate_adjacent_pairs": duplicates,
    }
    return rows, summary


def check_metadata(capture_root: Path, image_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Check per-sample metadata files."""
    metadata_dir = capture_root / "metadata"
    if not metadata_dir.exists():
        return {"metadata_dir_exists": False, "metadata_files": 0, "missing_metadata": len(image_rows), "invalid_metadata": 0}
    missing = 0
    invalid = 0
    for row in image_rows:
        sample_index = int(row["sample_index"])
        path = metadata_dir / f"sample_{sample_index:06d}.json"
        if not path.exists():
            missing += 1
            continue
        if load_json(path) is None:
            invalid += 1
    return {
        "metadata_dir_exists": True,
        "metadata_files": len(list(metadata_dir.glob("*.json"))),
        "missing_metadata": missing,
        "invalid_metadata": invalid,
    }


def judge_quality(
    *,
    image_count: int,
    damaged_images: int,
    resolution_mismatch: bool,
    blurry_count: int,
    blurry_fraction: float,
    duplicate_fraction: float,
    missing_metadata: int,
    capture_index_warnings: list[str],
    args: argparse.Namespace,
) -> tuple[str, list[str]]:
    """Return PASS/WARNING/FAIL and reasons."""
    fail_reasons: list[str] = []
    warning_reasons: list[str] = []
    if image_count < args.min_samples:
        fail_reasons.append("samples too few")
    if damaged_images:
        fail_reasons.append("damaged images found")
    if resolution_mismatch:
        fail_reasons.append("resolution mismatch")
    if blurry_fraction > args.max_blurry_fraction:
        fail_reasons.append("too many blurry images")
    if missing_metadata:
        warning_reasons.append("missing metadata")
    if capture_index_warnings:
        warning_reasons.append("capture_index.csv incomplete")
    if duplicate_fraction > args.max_duplicate_fraction:
        warning_reasons.append("duplicated samples")

    if fail_reasons:
        return "FAIL", fail_reasons + warning_reasons
    if warning_reasons or blurry_count > 0:
        return "WARNING", warning_reasons + (["some blurry images"] if blurry_count else [])
    return "PASS", []


def save_summary_csv(path: Path, summary: dict[str, Any]) -> None:
    """Save scalar summary metrics to CSV."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "value"])
        writer.writeheader()
        for key, value in summary.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                writer.writerow({"metric": key, "value": value})


def save_report(path: Path, summary: dict[str, Any], reasons: list[str]) -> None:
    """Write markdown report."""
    lines = [
        "# Capture Quality Report",
        "",
        f"- Capture root: `{summary['capture_root']}`",
        f"- Decision: **{summary['decision']}**",
        f"- Image count: {summary['image_count']}",
        f"- Damaged images: {summary['damaged_images']}",
        f"- Resolution mismatch: {summary['resolution_mismatch']}",
        f"- Blurry images: {summary['blurry_count']} ({summary['blurry_fraction']:.3f})",
        f"- Duplicate adjacent pairs: {summary['duplicate_adjacent_pairs']} ({summary['duplicate_fraction']:.3f})",
        f"- Missing metadata: {summary['missing_metadata']}",
        "",
        "## Reasons",
        "",
    ]
    if reasons:
        lines.extend(f"- {reason}" for reason in reasons)
    else:
        lines.append("- No blocking issues detected.")
    lines.extend(
        [
            "",
            "## Blur Stats",
            "",
            f"- {summary['blur_stats']}",
            "",
            "## Frame Difference Stats",
            "",
            f"- {summary['frame_difference_stats']}",
            "",
            "## Scene Change Stats",
            "",
            f"- {summary['scene_change_stats']}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def maybe_plot(output_dir: Path, image_rows: list[dict[str, Any]], images: list[Path]) -> list[str]:
    """Generate optional plots/contact sheet."""
    warnings: list[str] = []
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
        blur_values = [float(row["blur_score"]) for row in image_rows if row["readable"]]
        diff_values = [float(row["frame_difference_score"]) for row in image_rows if row["readable"] and int(row["sample_index"]) > 1]
        for values, title, filename in [
            (blur_values, "Blur Score Distribution", "blur_distribution.png"),
            (diff_values, "Frame Difference Distribution", "frame_difference_distribution.png"),
        ]:
            fig, ax = plt.subplots(figsize=(7, 4))
            ax.hist(values, bins=min(30, max(5, len(values)))) if values else ax.text(0.5, 0.5, "No values", ha="center")
            ax.set_title(title)
            ax.grid(True, alpha=0.3)
            fig.tight_layout()
            fig.savefig(output_dir / filename, dpi=150)
            plt.close(fig)
        save_contact_sheet(output_dir / "sample_contact_sheet.png", images)
        return warnings
    finally:
        tmp_dir.cleanup()
        if previous_mpl_config is None:
            import os

            os.environ.pop("MPLCONFIGDIR", None)
        else:
            import os

            os.environ["MPLCONFIGDIR"] = previous_mpl_config


def save_contact_sheet(path: Path, images: list[Path], max_images: int = 25) -> None:
    """Save a small thumbnail contact sheet."""
    selected = images[:max_images]
    if not selected:
        canvas = np.full((120, 240, 3), 240, dtype=np.uint8)
        cv2.putText(canvas, "No images", (35, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (40, 40, 40), 2)
        cv2.imwrite(str(path), canvas)
        return
    thumbs = []
    for image_path in selected:
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            image = np.full((96, 128, 3), 80, dtype=np.uint8)
        thumbs.append(cv2.resize(image, (128, 96)))
    cols = 5
    rows = int(np.ceil(len(thumbs) / cols))
    canvas = np.full((rows * 96, cols * 128, 3), 20, dtype=np.uint8)
    for idx, thumb in enumerate(thumbs):
        row = idx // cols
        col = idx % cols
        canvas[row * 96 : (row + 1) * 96, col * 128 : (col + 1) * 128] = thumb
    cv2.imwrite(str(path), canvas)


def main() -> None:
    """Run capture quality checks."""
    args = parse_args()
    capture_root = resolve_cli_path(args.capture_root, args.paths_config)
    output_dir = resolve_cli_path(args.output_dir, args.paths_config)

    if args.validate_config:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "capture_root": str(capture_root),
                    "capture_root_exists": capture_root.exists(),
                    "output_dir": str(output_dir),
                    "output_parent_exists": output_dir.parent.exists(),
                    "opencv_available": True,
                    "plot": bool(args.plot),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return None

    if not capture_root.exists():
        raise FileNotFoundError(f"Capture root not found: {capture_root}")
    output_dir.mkdir(parents=True, exist_ok=True)

    images = find_images(capture_root)
    index_rows, index_warnings = read_capture_index(capture_root)
    image_rows, image_summary = analyze_images(capture_root, images, args.duplicate_scene_threshold)
    metadata_summary = check_metadata(capture_root, image_rows)
    blur_values = [float(row["blur_score"]) for row in image_rows if row["readable"]]
    diff_values = [float(row["frame_difference_score"]) for row in image_rows if row["readable"] and int(row["sample_index"]) > 1]
    change_values = [float(row["scene_change_score"]) for row in image_rows if row["readable"] and int(row["sample_index"]) > 1]
    blurry_count = sum(1 for value in blur_values if value < args.blur_threshold)
    image_count = len(images)
    duplicate_pairs = int(image_summary["duplicate_adjacent_pairs"])
    blurry_fraction = blurry_count / max(image_count, 1)
    duplicate_fraction = duplicate_pairs / max(image_count - 1, 1)
    metadata_missing = int(metadata_summary["missing_metadata"])
    decision, reasons = judge_quality(
        image_count=image_count,
        damaged_images=int(image_summary["damaged_images"]),
        resolution_mismatch=bool(image_summary["resolution_mismatch"]),
        blurry_count=blurry_count,
        blurry_fraction=blurry_fraction,
        duplicate_fraction=duplicate_fraction,
        missing_metadata=metadata_missing,
        capture_index_warnings=index_warnings,
        args=args,
    )
    plot_warnings = maybe_plot(output_dir, image_rows, images) if args.plot else []

    summary = {
        "capture_root": str(capture_root),
        "decision": decision,
        "reasons": reasons,
        "image_count": image_count,
        "min_samples": args.min_samples,
        "capture_index_rows": len(index_rows),
        "capture_index_warnings": index_warnings,
        "damaged_images": int(image_summary["damaged_images"]),
        "resolution_counts": image_summary["resolution_counts"],
        "resolution_mismatch": bool(image_summary["resolution_mismatch"]),
        "blur_threshold": args.blur_threshold,
        "blurry_count": blurry_count,
        "blurry_fraction": blurry_fraction,
        "duplicate_scene_threshold": args.duplicate_scene_threshold,
        "duplicate_adjacent_pairs": duplicate_pairs,
        "duplicate_fraction": duplicate_fraction,
        "metadata_dir_exists": metadata_summary["metadata_dir_exists"],
        "metadata_files": metadata_summary["metadata_files"],
        "missing_metadata": metadata_missing,
        "invalid_metadata": metadata_summary["invalid_metadata"],
        "blur_stats": finite_stats(blur_values),
        "frame_difference_stats": finite_stats(diff_values),
        "scene_change_stats": finite_stats(change_values),
        "plot_warnings": plot_warnings,
    }

    (output_dir / "quality_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    save_summary_csv(output_dir / "quality_summary.csv", summary)
    save_report(output_dir / "capture_quality_report.md", summary, reasons)
    with (output_dir / "image_quality_rows.csv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(image_rows[0].keys()) if image_rows else [
            "sample_index",
            "image_path",
            "readable",
            "width",
            "height",
            "blur_score",
            "frame_difference_score",
            "scene_change_score",
            "too_similar_to_previous",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(image_rows)
    print(json.dumps({"status": "ok", "decision": decision, "output_dir": str(output_dir), "reasons": reasons}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
