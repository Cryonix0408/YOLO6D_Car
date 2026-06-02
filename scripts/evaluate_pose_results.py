"""本文件作用：
    评估 replay 输出 CSV 中 raw pose 与 filtered pose 的稳定性，并可选对比 GT。

在 YOLO6D_Car pipeline 中的位置：
    evaluation 阶段。通常在 replay 或 ablation 生成 pose_results.csv 后运行。

主要输入：
    --input-csv: replay 输出，至少包含 raw_tx/raw_ty/raw_tz/raw_rx/raw_ry/raw_rz。
    --gt-csv: 可选，第一版只支持预处理后的 gt_pose.csv。

主要输出：
    metrics_summary.json/csv、evaluation_report.md、可选图像；
    传入 GT 时额外输出 gt_metrics_summary.json/csv 和误差曲线。

注意事项：
    jitter 是帧间 pose 变化的 RMS，不等价于绝对精度；
    GT evaluation 不直接解析复杂 FzMotion 原始 CSV。
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.evaluation.metrics import (
    compute_acceleration,
    compute_jitter,
    compute_mean_abs_delta,
    compute_rmse,
    compute_velocity,
    norm_std,
    summarize_tracking_states,
)
from yolo6d_car.evaluation.gt_metrics import (
    align_gt_to_predictions,
    compute_gt_comparison,
    load_gt_pose_csv,
)
from yolo6d_car.evaluation.report import save_markdown_report, save_metrics_csv, save_metrics_json
from yolo6d_car.evaluation.trajectory import load_pose_csv
from yolo6d_car.path_utils import load_local_paths, resolve_path


def parse_args() -> argparse.Namespace:
    """Parse evaluation arguments."""
    parser = argparse.ArgumentParser(description="Compare raw and filtered replay pose stability.")
    parser.add_argument("--input-csv", "--csv", dest="input_csv", required=True, help="Replay output CSV.")
    parser.add_argument("--output-dir", "--out-dir", dest="output_dir", required=True, help="Evaluation output directory.")
    parser.add_argument("--paths-config", default=None, help="Optional local paths YAML, e.g. configs/paths_local.yaml.")
    parser.add_argument("--default-fps", type=float, default=30.0, help="Fallback FPS if timestamps are missing.")
    parser.add_argument("--plot", action="store_true", help="Generate PNG plots if matplotlib is available.")
    parser.add_argument("--gt-csv", default=None, help="Optional preprocessed GT CSV with timestamp, gt_tx..gt_rz columns.")
    parser.add_argument("--max-time-diff-s", type=float, default=0.03, help="Max nearest timestamp difference for GT matching.")
    parser.add_argument("--validate-config", action="store_true", help="Validate paths without writing reports.")
    return parser.parse_args()


def resolve_cli_path(raw_path: str, paths_config: str | None) -> Path:
    """Resolve CLI path through paths_local.yaml when provided."""
    local_paths = load_local_paths(paths_config) if paths_config else None
    path = resolve_path(raw_path, project_root=ROOT, local_paths=local_paths)
    if path is None:
        raise ValueError(f"Path is required: {raw_path}")
    return path.resolve()


def percent_improvement(raw_value: float, filtered_value: float) -> float:
    """Return positive percent when filtered metric is smaller than raw."""
    if abs(raw_value) < 1e-12:
        return 0.0
    return float((raw_value - filtered_value) / raw_value * 100.0)


def compute_metrics(data, input_csv: Path, default_fps: float, gt_csv: Path | None) -> dict[str, Any]:
    """计算 raw pose 与 filtered pose 的 jitter / smoothness 指标。

    raw pose:
        PnP 直接输出，反映单帧测量本身。
    filtered pose:
        Kalman 输出，反映时间滤波后的轨迹。
    """
    raw_translation = data.raw_pose[:, 0:3]
    raw_rotation = data.raw_pose[:, 3:6]

    raw_translation_velocity = compute_velocity(raw_translation, data.timestamps)
    raw_translation_accel = compute_acceleration(raw_translation, data.timestamps)

    raw_translation_jitter = compute_jitter(raw_translation)
    raw_rotation_jitter = compute_jitter(raw_rotation)
    raw_translation_accel_std = norm_std(raw_translation_accel)

    state_counts = summarize_tracking_states(data.tracking_states)
    valid_measurement_frames = int(sum(data.valid_measurements))
    predict_only_frames = int(state_counts.get("PREDICT_ONLY", 0))
    lost_frames = int(state_counts.get("LOST", 0))
    warnings = list(data.warnings)
    if gt_csv is not None:
        warnings.append(f"GT comparison requested; see gt_metrics_summary.json for GT accuracy metrics: {gt_csv}")

    if data.filtered_pose is None:
        warnings.append("filtered pose columns not found; reporting raw-only metrics.")
        metrics = {
            "input_csv": str(input_csv),
            "default_fps": float(default_fps),
            "total_frames": int(len(data.rows)),
            "valid_measurement_frames": valid_measurement_frames,
            "invalid_measurement_frames": int(len(data.rows) - valid_measurement_frames),
            "predict_only_frames": predict_only_frames,
            "lost_frames": lost_frames,
            "tracking_state_counts": state_counts,
            "raw_translation_jitter": raw_translation_jitter,
            "filtered_translation_jitter": None,
            "raw_rotation_jitter": raw_rotation_jitter,
            "filtered_rotation_jitter": None,
            "raw_translation_velocity_std": norm_std(raw_translation_velocity),
            "filtered_translation_velocity_std": None,
            "raw_translation_acceleration_std": raw_translation_accel_std,
            "filtered_translation_acceleration_std": None,
            "jitter_reduction_percent": None,
            "rotation_jitter_reduction_percent": None,
            "acceleration_smoothness_improvement_percent": None,
            "raw_filtered_translation_rmse": None,
            "raw_filtered_rotation_rmse": None,
            "raw_translation_mean_abs_delta": compute_mean_abs_delta(raw_translation),
            "filtered_translation_mean_abs_delta": None,
            "warnings": warnings,
        }
        metrics.update(compute_reliability_metrics(data))
        return metrics

    filtered_translation = data.filtered_pose[:, 0:3]
    filtered_rotation = data.filtered_pose[:, 3:6]
    filtered_translation_velocity = compute_velocity(filtered_translation, data.timestamps)
    filtered_translation_accel = compute_acceleration(filtered_translation, data.timestamps)
    filtered_translation_jitter = compute_jitter(filtered_translation)
    filtered_rotation_jitter = compute_jitter(filtered_rotation)
    filtered_translation_accel_std = norm_std(filtered_translation_accel)

    metrics = {
        "input_csv": str(input_csv),
        "default_fps": float(default_fps),
        "total_frames": int(len(data.rows)),
        "valid_measurement_frames": valid_measurement_frames,
        "invalid_measurement_frames": int(len(data.rows) - valid_measurement_frames),
        "predict_only_frames": predict_only_frames,
        "lost_frames": lost_frames,
        "tracking_state_counts": state_counts,
        "raw_translation_jitter": raw_translation_jitter,
        "filtered_translation_jitter": filtered_translation_jitter,
        "raw_rotation_jitter": raw_rotation_jitter,
        "filtered_rotation_jitter": filtered_rotation_jitter,
        "raw_translation_velocity_std": norm_std(raw_translation_velocity),
        "filtered_translation_velocity_std": norm_std(filtered_translation_velocity),
        "raw_translation_acceleration_std": raw_translation_accel_std,
        "filtered_translation_acceleration_std": filtered_translation_accel_std,
        "jitter_reduction_percent": percent_improvement(raw_translation_jitter, filtered_translation_jitter),
        "rotation_jitter_reduction_percent": percent_improvement(raw_rotation_jitter, filtered_rotation_jitter),
        "acceleration_smoothness_improvement_percent": percent_improvement(
            raw_translation_accel_std,
            filtered_translation_accel_std,
        ),
        "raw_filtered_translation_rmse": compute_rmse(raw_translation, filtered_translation),
        "raw_filtered_rotation_rmse": compute_rmse(raw_rotation, filtered_rotation),
        "raw_translation_mean_abs_delta": compute_mean_abs_delta(raw_translation),
        "filtered_translation_mean_abs_delta": compute_mean_abs_delta(filtered_translation),
        "warnings": warnings,
    }
    metrics.update(compute_reliability_metrics(data))
    return metrics


def compute_reliability_metrics(data) -> dict[str, Any]:
    """Summarize optional reliability-aware Kalman CSV fields."""
    headers = set(data.headers)
    if "reliability_score" not in headers and "dynamic_R_scale" not in headers:
        return {}

    def finite_column(name: str) -> np.ndarray:
        values: list[float] = []
        for row in data.rows:
            try:
                value = float(row.get(name, ""))
            except ValueError:
                continue
            if np.isfinite(value):
                values.append(value)
        return np.asarray(values, dtype=np.float64)

    def bool_column(name: str) -> list[bool]:
        return [str(row.get(name, "")).strip().lower() in {"1", "true", "yes", "y"} for row in data.rows]

    reliability = finite_column("reliability_score")
    dynamic_r = finite_column("dynamic_R_scale")
    valid_measurement = bool_column("valid_measurement") if "valid_measurement" in headers else data.valid_measurements
    reject_reasons = [row.get("reject_reason", "").strip() for row in data.rows if row.get("reject_reason", "").strip()]

    summary: dict[str, Any] = {
        "rejected_measurement_frames": int(sum(not value for value in valid_measurement)) if valid_measurement else 0,
        "top_reject_reasons": dict(Counter(reject_reasons).most_common(5)),
    }
    if reliability.size:
        summary.update(
            {
                "mean_reliability_score": float(np.mean(reliability)),
                "min_reliability_score": float(np.min(reliability)),
                "max_reliability_score": float(np.max(reliability)),
            }
        )
    if dynamic_r.size:
        summary["mean_dynamic_R_scale"] = float(np.mean(dynamic_r))
    return summary


def compute_gt_metrics(data, gt_csv: Path, max_time_diff_s: float) -> tuple[dict[str, Any], dict[str, list[float]]]:
    """Compute raw/filtered prediction accuracy against preprocessed GT poses."""
    gt_data = load_gt_pose_csv(gt_csv)
    aligned = align_gt_to_predictions(data.timestamps, gt_data, max_time_diff_s=max_time_diff_s)
    metrics: dict[str, Any] = {
        "gt_csv": str(gt_csv),
        "gt_format": "timestamp,gt_tx,gt_ty,gt_tz,gt_rx,gt_ry,gt_rz",
        "max_time_diff_s": float(max_time_diff_s),
        "prediction_frames": int(len(data.rows)),
        "gt_frames": int(len(gt_data.timestamps)),
        "matched_frames": int(len(aligned.prediction_indices)),
    }
    if aligned.time_diffs_s.size:
        metrics.update(
            {
                "mean_match_time_diff_s": float(np.mean(aligned.time_diffs_s)),
                "max_match_time_diff_s": float(np.max(aligned.time_diffs_s)),
            }
        )
    else:
        metrics.update({"mean_match_time_diff_s": None, "max_match_time_diff_s": None})

    raw_metrics, raw_series = compute_gt_comparison("raw", data.raw_pose, aligned)
    metrics.update(raw_metrics)
    series = dict(raw_series)
    if data.filtered_pose is None:
        metrics["filtered_gt_warning"] = "filtered pose columns not found; run replay with --kalman-config first."
    else:
        filtered_metrics, filtered_series = compute_gt_comparison("filtered", data.filtered_pose, aligned)
        metrics.update(filtered_metrics)
        for key, value in filtered_series.items():
            if key == "timestamp" and "timestamp" in series:
                continue
            series[key] = value
    return metrics, series


def save_gt_series_csv(path: Path, series: dict[str, list[float]]) -> None:
    """Save per-frame GT error series as CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not series or "timestamp" not in series:
        path.write_text("timestamp\n", encoding="utf-8")
        return
    import csv

    headers = ["timestamp", *[key for key in series.keys() if key != "timestamp"]]
    row_count = len(series["timestamp"])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for index in range(row_count):
            row = {}
            for header in headers:
                values = series.get(header, [])
                row[header] = values[index] if index < len(values) else ""
            writer.writerow(row)


def save_gt_markdown_report(path: Path, metrics: dict[str, Any]) -> None:
    """Save a short GT comparison markdown report."""
    lines = [
        "# Mocap GT Evaluation",
        "",
        f"- GT CSV: `{metrics.get('gt_csv')}`",
        f"- Max time difference: {metrics.get('max_time_diff_s')} s",
        f"- Prediction frames: {metrics.get('prediction_frames')}",
        f"- GT frames: {metrics.get('gt_frames')}",
        f"- Matched frames: {metrics.get('matched_frames')}",
        "",
        "## Raw vs GT",
        "",
        f"- Translation RMSE: {metrics.get('raw_translation_rmse')}",
        f"- ATE: {metrics.get('raw_ate')}",
        f"- Rotation error mean rad: {metrics.get('raw_rotation_error_mean_rad')}",
        f"- Rotation error median rad: {metrics.get('raw_rotation_error_median_rad')}",
        f"- Rotation error max rad: {metrics.get('raw_rotation_error_max_rad')}",
        f"- RPE translation mean: {metrics.get('raw_rpe_translation_mean')}",
        f"- RPE rotation mean rad: {metrics.get('raw_rpe_rotation_mean_rad')}",
        f"- Per-axis RMSE: tx={metrics.get('raw_tx_rmse')}, ty={metrics.get('raw_ty_rmse')}, tz={metrics.get('raw_tz_rmse')}",
        "",
        "## Filtered vs GT",
        "",
        f"- Translation RMSE: {metrics.get('filtered_translation_rmse')}",
        f"- ATE: {metrics.get('filtered_ate')}",
        f"- Rotation error mean rad: {metrics.get('filtered_rotation_error_mean_rad')}",
        f"- Rotation error median rad: {metrics.get('filtered_rotation_error_median_rad')}",
        f"- Rotation error max rad: {metrics.get('filtered_rotation_error_max_rad')}",
        f"- RPE translation mean: {metrics.get('filtered_rpe_translation_mean')}",
        f"- RPE rotation mean rad: {metrics.get('filtered_rpe_rotation_mean_rad')}",
        f"- Per-axis RMSE: tx={metrics.get('filtered_tx_rmse')}, ty={metrics.get('filtered_ty_rmse')}, tz={metrics.get('filtered_tz_rmse')}",
    ]
    if metrics.get("filtered_gt_warning"):
        lines.extend(["", "## Warnings", "", f"- {metrics['filtered_gt_warning']}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_matplotlib() -> tuple[Any | None, Any | None, tempfile.TemporaryDirectory[str] | None, str | None, list[str]]:
    """Load matplotlib with a temporary config directory."""
    previous_mpl_config = os.environ.get("MPLCONFIGDIR")
    try:
        tmp_dir_ctx = tempfile.TemporaryDirectory(prefix="yolo6d_mpl_")
        os.environ["MPLCONFIGDIR"] = tmp_dir_ctx.name
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        return matplotlib, plt, tmp_dir_ctx, previous_mpl_config, []
    except Exception as exc:
        if previous_mpl_config is None:
            os.environ.pop("MPLCONFIGDIR", None)
        else:
            os.environ["MPLCONFIGDIR"] = previous_mpl_config
        return None, None, None, previous_mpl_config, [f"Plotting skipped because matplotlib is unavailable: {exc}"]


def _cleanup_matplotlib(tmp_dir_ctx: tempfile.TemporaryDirectory[str] | None, previous_mpl_config: str | None) -> None:
    """Clean temporary matplotlib config."""
    if tmp_dir_ctx is not None:
        tmp_dir_ctx.cleanup()
    if previous_mpl_config is None:
        os.environ.pop("MPLCONFIGDIR", None)
    else:
        os.environ["MPLCONFIGDIR"] = previous_mpl_config


def maybe_make_plots(data, output_dir: Path, metrics: dict[str, Any]) -> list[str]:
    """Create optional matplotlib plots; return warning strings on failure."""
    warnings: list[str] = []
    _, plt, tmp_dir_ctx, previous_mpl_config, load_warnings = _load_matplotlib()
    if load_warnings:
        return load_warnings

    try:
        if data.filtered_pose is None:
            return ["Plotting skipped because filtered pose is missing."]

        t = data.timestamps
        raw_t = data.raw_pose[:, 0:3]
        raw_r = data.raw_pose[:, 3:6]
        filt_t = data.filtered_pose[:, 0:3]
        filt_r = data.filtered_pose[:, 3:6]

        def save_xyz(path: str, title: str, raw: np.ndarray, filtered: np.ndarray, labels: tuple[str, str, str]) -> None:
            fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
            for idx, axis in enumerate(axes):
                axis.plot(t, raw[:, idx], label=f"raw {labels[idx]}", linewidth=1.2)
                axis.plot(t, filtered[:, idx], label=f"filtered {labels[idx]}", linewidth=1.2)
                axis.legend()
                axis.grid(True, alpha=0.3)
            axes[0].set_title(title)
            axes[-1].set_xlabel("time (s)")
            fig.tight_layout()
            fig.savefig(output_dir / path, dpi=150)
            plt.close(fig)

        save_xyz("translation_xyz_raw_vs_filtered.png", "Translation Raw vs Filtered", raw_t, filt_t, ("x", "y", "z"))
        save_xyz("rotation_rvec_raw_vs_filtered.png", "Rotation Vector Raw vs Filtered", raw_r, filt_r, ("rx", "ry", "rz"))

        raw_v = compute_velocity(raw_t, t)
        filt_v = compute_velocity(filt_t, t)
        raw_a = compute_acceleration(raw_t, t)
        filt_a = compute_acceleration(filt_t, t)
        tv = t[1 : 1 + raw_v.shape[0]]
        ta = t[2 : 2 + raw_a.shape[0]]

        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(tv, np.linalg.norm(raw_v, axis=1), label="raw velocity")
        ax.plot(tv, np.linalg.norm(filt_v, axis=1), label="filtered velocity")
        ax.set_title("Translation Velocity Norm")
        ax.set_xlabel("time (s)")
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(output_dir / "translation_velocity.png", dpi=150)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(ta, np.linalg.norm(raw_a, axis=1), label="raw acceleration")
        ax.plot(ta, np.linalg.norm(filt_a, axis=1), label="filtered acceleration")
        ax.set_title("Translation Acceleration Norm")
        ax.set_xlabel("time (s)")
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(output_dir / "translation_acceleration.png", dpi=150)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(7, 4))
        names = ["translation jitter", "rotation jitter"]
        raw_vals = [metrics["raw_translation_jitter"], metrics["raw_rotation_jitter"]]
        filt_vals = [metrics["filtered_translation_jitter"], metrics["filtered_rotation_jitter"]]
        x = np.arange(len(names))
        ax.bar(x - 0.18, raw_vals, width=0.36, label="raw")
        ax.bar(x + 0.18, filt_vals, width=0.36, label="filtered")
        ax.set_xticks(x, names)
        ax.set_title("Jitter Comparison")
        ax.grid(True, axis="y", alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(output_dir / "jitter_comparison.png", dpi=150)
        plt.close(fig)

        state_to_int = {state: idx for idx, state in enumerate(sorted(set(data.tracking_states)))}
        fig, ax = plt.subplots(figsize=(10, 3))
        ax.step(t, [state_to_int.get(s, 0) for s in data.tracking_states], where="post")
        ax.set_yticks(list(state_to_int.values()), list(state_to_int.keys()))
        ax.set_title("Tracking State Timeline")
        ax.set_xlabel("time (s)")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_dir / "tracking_state_timeline.png", dpi=150)
        plt.close(fig)
        return warnings
    finally:
        _cleanup_matplotlib(tmp_dir_ctx, previous_mpl_config)


def maybe_make_gt_plots(data, gt_csv: Path, output_dir: Path, gt_metrics: dict[str, Any], gt_series: dict[str, list[float]], max_time_diff_s: float) -> list[str]:
    """Create GT comparison and error-over-time plots."""
    _, plt, tmp_dir_ctx, previous_mpl_config, load_warnings = _load_matplotlib()
    if load_warnings:
        return load_warnings

    try:
        gt_data = load_gt_pose_csv(gt_csv)
        aligned = align_gt_to_predictions(data.timestamps, gt_data, max_time_diff_s=max_time_diff_s)
        if aligned.prediction_indices.size == 0:
            return ["GT plotting skipped because no timestamps matched within max_time_diff_s."]
        t = aligned.prediction_timestamps
        raw_pose = data.raw_pose[aligned.prediction_indices]
        gt_pose = aligned.gt_pose
        filtered_pose = None if data.filtered_pose is None else data.filtered_pose[aligned.prediction_indices]

        def plot_xyz(filename: str, title: str, pred_cols: slice, gt_cols: slice, labels: tuple[str, str, str]) -> None:
            fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
            for idx, axis in enumerate(axes):
                axis.plot(t, raw_pose[:, pred_cols][..., idx], label=f"raw {labels[idx]}", linewidth=1.0)
                if filtered_pose is not None:
                    axis.plot(t, filtered_pose[:, pred_cols][..., idx], label=f"filtered {labels[idx]}", linewidth=1.0)
                axis.plot(t, gt_pose[:, gt_cols][..., idx], label=f"GT {labels[idx]}", linewidth=1.0, linestyle="--")
                axis.legend()
                axis.grid(True, alpha=0.3)
            axes[0].set_title(title)
            axes[-1].set_xlabel("time (s)")
            fig.tight_layout()
            fig.savefig(output_dir / filename, dpi=150)
            plt.close(fig)

        plot_xyz("gt_translation_raw_filtered.png", "Translation Raw/Filtered vs GT", slice(0, 3), slice(0, 3), ("x", "y", "z"))
        plot_xyz("gt_rotation_raw_filtered.png", "Rotation Vector Raw/Filtered vs GT", slice(3, 6), slice(3, 6), ("rx", "ry", "rz"))

        timestamps = np.asarray(gt_series.get("timestamp", []), dtype=np.float64)
        fig, ax = plt.subplots(figsize=(10, 4))
        if "raw_translation_error" in gt_series:
            ax.plot(timestamps, gt_series["raw_translation_error"], label="raw translation error")
        if "filtered_translation_error" in gt_series:
            ax.plot(timestamps, gt_series["filtered_translation_error"], label="filtered translation error")
        ax.set_title("Translation Error Over Time")
        ax.set_xlabel("time (s)")
        ax.set_ylabel("meters")
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(output_dir / "gt_translation_error_over_time.png", dpi=150)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(10, 4))
        if "raw_rotation_error_rad" in gt_series:
            ax.plot(timestamps, gt_series["raw_rotation_error_rad"], label="raw rotation error")
        if "filtered_rotation_error_rad" in gt_series:
            ax.plot(timestamps, gt_series["filtered_rotation_error_rad"], label="filtered rotation error")
        ax.set_title("Rotation Error Over Time")
        ax.set_xlabel("time (s)")
        ax.set_ylabel("radians")
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(output_dir / "gt_rotation_error_over_time.png", dpi=150)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(7, 4))
        names = ["translation RMSE", "rotation mean"]
        raw_vals = [gt_metrics.get("raw_translation_rmse") or 0.0, gt_metrics.get("raw_rotation_error_mean_rad") or 0.0]
        filt_vals = [gt_metrics.get("filtered_translation_rmse") or 0.0, gt_metrics.get("filtered_rotation_error_mean_rad") or 0.0]
        x = np.arange(len(names))
        ax.bar(x - 0.18, raw_vals, width=0.36, label="raw")
        ax.bar(x + 0.18, filt_vals, width=0.36, label="filtered")
        ax.set_xticks(x, names)
        ax.set_title("GT Error Summary")
        ax.grid(True, axis="y", alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(output_dir / "gt_error_summary.png", dpi=150)
        plt.close(fig)
        return []
    finally:
        _cleanup_matplotlib(tmp_dir_ctx, previous_mpl_config)


def main() -> None:
    """Evaluate pose CSV and write metrics reports."""
    args = parse_args()
    input_csv = resolve_cli_path(args.input_csv, args.paths_config)
    output_dir = resolve_cli_path(args.output_dir, args.paths_config)
    gt_csv = resolve_cli_path(args.gt_csv, args.paths_config) if args.gt_csv else None

    if args.validate_config:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "input_csv": str(input_csv),
                    "input_csv_exists": input_csv.exists(),
                    "output_dir": str(output_dir),
                    "output_parent_exists": output_dir.parent.exists(),
                    "gt_csv": None if gt_csv is None else str(gt_csv),
                    "gt_csv_exists": None if gt_csv is None else gt_csv.exists(),
                    "max_time_diff_s": args.max_time_diff_s,
                    "default_fps": args.default_fps,
                    "plot": args.plot,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return None

    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")
    output_dir.mkdir(parents=True, exist_ok=True)

    data = load_pose_csv(input_csv, default_fps=args.default_fps)
    metrics = compute_metrics(data, input_csv, args.default_fps, gt_csv)
    gt_metrics: dict[str, Any] | None = None
    gt_series: dict[str, list[float]] | None = None
    if gt_csv is not None:
        if not gt_csv.exists():
            raise FileNotFoundError(f"GT CSV not found: {gt_csv}")
        try:
            gt_metrics, gt_series = compute_gt_metrics(data, gt_csv, args.max_time_diff_s)
        except RuntimeError as exc:
            raise SystemExit(f"ERROR: {exc}") from None
        save_metrics_json(output_dir / "gt_metrics_summary.json", gt_metrics)
        save_metrics_csv(output_dir / "gt_metrics_summary.csv", gt_metrics)
        save_gt_series_csv(output_dir / "gt_error_timeseries.csv", gt_series)
        save_gt_markdown_report(output_dir / "gt_evaluation_report.md", gt_metrics)
    if args.plot:
        metrics["warnings"].extend(maybe_make_plots(data, output_dir, metrics))
        if gt_csv is not None and gt_metrics is not None and gt_series is not None:
            metrics["warnings"].extend(maybe_make_gt_plots(data, gt_csv, output_dir, gt_metrics, gt_series, args.max_time_diff_s))

    save_metrics_json(output_dir / "metrics_summary.json", metrics)
    save_metrics_csv(output_dir / "metrics_summary.csv", metrics)
    save_markdown_report(output_dir / "evaluation_report.md", metrics)
    print(json.dumps({"status": "ok", "output_dir": str(output_dir), "metrics": metrics}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
