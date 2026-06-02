"""本文件作用：
    把 evaluation 指标写成 JSON、CSV 和 Markdown 报告。

在 YOLO6D_Car pipeline 中的位置：
    evaluation 的输出层。指标计算完成后统一从这里落盘，便于 ablation 和论文表格复用。

注意事项：
    CSV 只写顶层标量，复杂 dict/list 会留在 JSON 中；
    Markdown 面向人工阅读，适合快速检查 raw vs filtered 的效果。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def save_metrics_json(path: str | Path, metrics: dict[str, Any]) -> None:
    """Save metrics as JSON."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")


def save_metrics_csv(path: str | Path, metrics: dict[str, Any]) -> None:
    """Save top-level scalar metrics as CSV."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    scalar_items = []
    for key, value in metrics.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            scalar_items.append({"metric": key, "value": value})
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "value"])
        writer.writeheader()
        writer.writerows(scalar_items)


def save_markdown_report(path: str | Path, metrics: dict[str, Any]) -> None:
    """Save a human-readable markdown report."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Pose Results Evaluation",
        "",
        f"- Input CSV: `{metrics.get('input_csv', '')}`",
        f"- Total frames: {metrics.get('total_frames', 0)}",
        f"- Valid measurement frames: {metrics.get('valid_measurement_frames', 0)}",
        f"- Predict-only frames: {metrics.get('predict_only_frames', 0)}",
        f"- Lost frames: {metrics.get('lost_frames', 0)}",
        "",
        "## Jitter",
        "",
        f"- Raw translation jitter: {metrics.get('raw_translation_jitter')}",
        f"- Filtered translation jitter: {metrics.get('filtered_translation_jitter')}",
        f"- Raw rotation jitter: {metrics.get('raw_rotation_jitter')}",
        f"- Filtered rotation jitter: {metrics.get('filtered_rotation_jitter')}",
        f"- Jitter reduction percent: {metrics.get('jitter_reduction_percent')}",
        "",
        "## Smoothness",
        "",
        f"- Raw translation velocity std: {metrics.get('raw_translation_velocity_std')}",
        f"- Filtered translation velocity std: {metrics.get('filtered_translation_velocity_std')}",
        f"- Raw translation acceleration std: {metrics.get('raw_translation_acceleration_std')}",
        f"- Filtered translation acceleration std: {metrics.get('filtered_translation_acceleration_std')}",
        f"- Acceleration smoothness improvement percent: {metrics.get('acceleration_smoothness_improvement_percent')}",
        "",
        "## Tracking States",
        "",
    ]
    for state, count in sorted((metrics.get("tracking_state_counts") or {}).items()):
        lines.append(f"- {state or '<empty>'}: {count}")
    if "mean_reliability_score" in metrics or "mean_dynamic_R_scale" in metrics:
        lines.extend(["", "## Reliability-Aware Kalman", ""])
        lines.append(f"- Mean reliability score: {metrics.get('mean_reliability_score')}")
        lines.append(f"- Min reliability score: {metrics.get('min_reliability_score')}")
        lines.append(f"- Max reliability score: {metrics.get('max_reliability_score')}")
        lines.append(f"- Mean dynamic R scale: {metrics.get('mean_dynamic_R_scale')}")
        lines.append(f"- Rejected measurement frames: {metrics.get('rejected_measurement_frames', 0)}")
        top_reasons = metrics.get("top_reject_reasons") or {}
        if top_reasons:
            lines.extend(["", "Top reject reasons:", ""])
            for reason, count in sorted(top_reasons.items(), key=lambda item: (-item[1], item[0])):
                lines.append(f"- {reason}: {count}")
    warnings = metrics.get("warnings") or []
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
