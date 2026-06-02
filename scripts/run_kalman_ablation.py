"""本文件作用：
    一键运行 raw_pnp / fixed_kf / reliability_kf 三种 replay 方法并汇总指标。

在 YOLO6D_Car pipeline 中的位置：
    ablation 阶段。通常在 replay pipeline 可运行后，用于比较不同 tracking 策略。

三种方法：
    raw_pnp: 不传 Kalman 配置，只评估 PnP 原始输出。
    fixed_kf: 使用 configs/kalman_fixed.yaml，R/Q 固定。
    reliability_kf: 使用 configs/kalman_reliability.yaml，根据观测质量动态缩放 R。

主要输出：
    outputs/ablation_runs/<run_name>/<method>/pose_results.csv
    results/ablation_reports/<run_name>/ablation_summary.csv/md/json

注意事项：
    smoke 数据帧数很少，只能验证流程；真实论文结论需要真实 fast-moving session。
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.path_utils import load_local_paths, resolve_path


SUMMARY_FIELDS = [
    "method",
    "status",
    "total_frames",
    "raw_translation_jitter",
    "filtered_translation_jitter",
    "raw_rotation_jitter",
    "filtered_rotation_jitter",
    "raw_translation_velocity_std",
    "filtered_translation_velocity_std",
    "raw_translation_acceleration_std",
    "filtered_translation_acceleration_std",
    "jitter_reduction_percent",
    "acceleration_smoothness_improvement_percent",
    "predict_only_frames",
    "lost_frames",
    "rejected_measurement_frames",
    "mean_reliability_score",
    "mean_dynamic_R_scale",
    "pose_csv",
    "evaluation_dir",
    "error",
]


@dataclass(frozen=True, slots=True)
class AblationMethod:
    """One replay method in the ablation."""

    name: str
    kalman_config: str | None


def parse_args() -> argparse.Namespace:
    """Parse ablation CLI arguments."""
    parser = argparse.ArgumentParser(description="Run raw PnP vs fixed KF vs reliability-aware KF replay ablation.")
    parser.add_argument("--config", required=True, help="Replay YAML config, e.g. configs/local_smoke_replay.yaml.")
    parser.add_argument("--paths-config", default=None, help="Optional paths YAML, e.g. configs/paths_local.yaml.")
    parser.add_argument("--run-name", default="smoke_kalman_ablation", help="Name for output folders.")
    parser.add_argument("--max-frames", type=int, default=3, help="Maximum replay frames per method.")
    parser.add_argument("--plot", action="store_true", help="Ask evaluator to generate plots when matplotlib is available.")
    parser.add_argument("--python", default=sys.executable, help="Python executable to run child scripts.")
    return parser.parse_args()


def resolve_cli_path(raw_path: str, paths_config: str | None) -> Path:
    """Resolve a path using paths_local.yaml when provided."""
    local_paths = load_local_paths(paths_config) if paths_config else None
    path = resolve_path(raw_path, project_root=ROOT, local_paths=local_paths)
    if path is None:
        raise ValueError(f"Path is required: {raw_path}")
    return path.resolve()


def run_command(command: list[str]) -> tuple[bool, str]:
    """Run a child command and return success plus combined output."""
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    output = "\n".join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part)
    return completed.returncode == 0, output


def load_metrics(metrics_path: Path) -> dict[str, Any]:
    """Load evaluator metrics JSON if present."""
    if not metrics_path.exists():
        raise FileNotFoundError(f"metrics_summary.json not found: {metrics_path}")
    return json.loads(metrics_path.read_text(encoding="utf-8"))


def summarize_method(
    method: AblationMethod,
    status: str,
    pose_csv: str,
    evaluation_dir: str,
    metrics: dict[str, Any] | None,
    error: str = "",
) -> dict[str, Any]:
    """Build one summary row from evaluator metrics."""
    row = {field: "" for field in SUMMARY_FIELDS}
    row.update(
        {
            "method": method.name,
            "status": status,
            "pose_csv": pose_csv,
            "evaluation_dir": evaluation_dir,
            "error": error,
        }
    )
    if metrics is None:
        return row
    for field in SUMMARY_FIELDS:
        if field in metrics:
            row[field] = metrics[field]
    return row


def write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write ablation summary CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_summary_json(path: Path, payload: dict[str, Any]) -> None:
    """Write ablation summary JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _metric_as_float(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    if value in {None, "", "N/A"}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _best_method(rows: list[dict[str, Any]], filtered_key: str, raw_key: str) -> tuple[str, float | None]:
    candidates: list[tuple[str, float]] = []
    for row in rows:
        if row.get("status") != "ok":
            continue
        value = _metric_as_float(row, filtered_key)
        if value is None:
            value = _metric_as_float(row, raw_key)
        if value is not None:
            candidates.append((str(row.get("method", "")), value))
    if not candidates:
        return "N/A", None
    return min(candidates, key=lambda item: item[1])


def _display_value(value: Any) -> str:
    """Format empty/None metric cells for markdown."""
    if value is None or value == "":
        return "N/A"
    return str(value)


def write_summary_markdown(
    path: Path,
    *,
    args: argparse.Namespace,
    rows: list[dict[str, Any]],
    output_dirs: dict[str, str],
) -> None:
    """Write human-readable ablation report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    best_jitter_method, best_jitter_value = _best_method(rows, "filtered_translation_jitter", "raw_translation_jitter")
    best_accel_method, best_accel_value = _best_method(
        rows,
        "filtered_translation_acceleration_std",
        "raw_translation_acceleration_std",
    )
    reliability_row = next((row for row in rows if row.get("method") == "reliability_kf"), {})

    lines = [
        "# Kalman Ablation Summary",
        "",
        "## Experiment Config",
        "",
        f"- Replay config: `{args.config}`",
        f"- Paths config: `{args.paths_config or ''}`",
        f"- Run name: `{args.run_name}`",
        f"- Max frames: {args.max_frames}",
        f"- Plot: {bool(args.plot)}",
        "",
        "## Output Paths",
        "",
    ]
    for method, output_dir in output_dirs.items():
        lines.append(f"- {method}: `{output_dir}`")

    lines.extend(
        [
            "",
            "## Metrics",
            "",
            "| method | status | total_frames | raw_translation_jitter | filtered_translation_jitter | jitter_reduction_percent | acceleration_smoothness_improvement_percent | predict_only_frames | lost_frames | rejected_measurement_frames | mean_reliability_score | mean_dynamic_R_scale |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    table_fields = [
        "method",
        "status",
        "total_frames",
        "raw_translation_jitter",
        "filtered_translation_jitter",
        "jitter_reduction_percent",
        "acceleration_smoothness_improvement_percent",
        "predict_only_frames",
        "lost_frames",
        "rejected_measurement_frames",
        "mean_reliability_score",
        "mean_dynamic_R_scale",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_display_value(row.get(field, "")) for field in table_fields) + " |")

    lines.extend(
        [
            "",
            "## Quick Read",
            "",
            f"- Lowest translation jitter: {best_jitter_method} ({best_jitter_value if best_jitter_value is not None else 'N/A'})",
            f"- Best acceleration smoothness: {best_accel_method} ({best_accel_value if best_accel_value is not None else 'N/A'})",
            f"- Reliability-aware mean reliability score: {_display_value(reliability_row.get('mean_reliability_score', ''))}",
            f"- Reliability-aware rejected frames: {_display_value(reliability_row.get('rejected_measurement_frames', ''))}",
            "",
            "## Notes",
            "",
            "- Smoke data has very few frames, so this report only checks the experiment machinery.",
            "- Real fast-moving data should be collected and replayed before drawing performance conclusions.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """Run the full three-way ablation."""
    args = parse_args()
    if args.max_frames <= 0:
        raise SystemExit("--max-frames must be greater than 0")

    methods = [
        AblationMethod("raw_pnp", None),
        AblationMethod("fixed_kf", "configs/kalman_fixed.yaml"),
        AblationMethod("reliability_kf", "configs/kalman_reliability.yaml"),
    ]
    summary_rows: list[dict[str, Any]] = []
    method_outputs: dict[str, str] = {}
    command_log: dict[str, dict[str, Any]] = {}

    for method in methods:
        replay_dir = f"outputs/ablation_runs/{args.run_name}/{method.name}"
        pose_csv = f"{replay_dir}/pose_results.csv"
        eval_dir = f"results/ablation_reports/{args.run_name}/{method.name}"
        method_outputs[method.name] = str(resolve_cli_path(replay_dir, args.paths_config))

        replay_command = [
            args.python,
            "scripts/smoke_replay_pipeline.py",
            "--config",
            args.config,
            "--max-frames",
            str(args.max_frames),
            "--output-csv",
            pose_csv,
        ]
        if args.paths_config:
            replay_command.extend(["--paths-config", args.paths_config])
        if method.kalman_config:
            replay_command.extend(["--kalman-config", method.kalman_config])

        replay_ok, replay_output = run_command(replay_command)
        command_log[f"{method.name}_replay"] = {
            "command": replay_command,
            "ok": replay_ok,
            "output": replay_output,
        }
        if not replay_ok:
            summary_rows.append(summarize_method(method, "replay_failed", pose_csv, eval_dir, None, replay_output))
            continue

        eval_command = [
            args.python,
            "scripts/evaluate_pose_results.py",
            "--input-csv",
            pose_csv,
            "--output-dir",
            eval_dir,
        ]
        if args.paths_config:
            eval_command.extend(["--paths-config", args.paths_config])
        if args.plot:
            eval_command.append("--plot")

        eval_ok, eval_output = run_command(eval_command)
        command_log[f"{method.name}_evaluation"] = {
            "command": eval_command,
            "ok": eval_ok,
            "output": eval_output,
        }
        if not eval_ok:
            summary_rows.append(summarize_method(method, "evaluation_failed", pose_csv, eval_dir, None, eval_output))
            continue

        try:
            metrics = load_metrics(resolve_cli_path(f"{eval_dir}/metrics_summary.json", args.paths_config))
            summary_rows.append(summarize_method(method, "ok", pose_csv, eval_dir, metrics))
        except Exception as exc:
            summary_rows.append(summarize_method(method, "metrics_failed", pose_csv, eval_dir, None, str(exc)))

    report_dir = resolve_cli_path(f"results/ablation_reports/{args.run_name}", args.paths_config)
    summary_payload = {
        "config": args.config,
        "paths_config": args.paths_config,
        "run_name": args.run_name,
        "max_frames": args.max_frames,
        "plot": bool(args.plot),
        "methods": summary_rows,
        "commands": command_log,
    }
    write_summary_csv(report_dir / "ablation_summary.csv", summary_rows)
    write_summary_json(report_dir / "ablation_summary.json", summary_payload)
    write_summary_markdown(report_dir / "ablation_summary.md", args=args, rows=summary_rows, output_dirs=method_outputs)

    print(
        json.dumps(
            {
                "status": "ok",
                "report_dir": str(report_dir),
                "summary_csv": str(report_dir / "ablation_summary.csv"),
                "summary_md": str(report_dir / "ablation_summary.md"),
                "methods": [{row["method"]: row["status"]} for row in summary_rows],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
