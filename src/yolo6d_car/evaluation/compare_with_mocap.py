"""本文件作用：
    预留给“直接与 Mocap 输出对比”的评估模块。

在 YOLO6D_Car pipeline 中的位置：
    evaluation 层。当前正式 GT 对比入口是 gt_metrics.py + evaluate_pose_results.py，
    只支持预处理后的 gt_pose.csv。

当前状态：
    placeholder。未来可以在这里实现从 FzMotion 原始 CSV 到 GT pose 的转换、
    时间同步、坐标系对齐和更完整的 Mocap 误差分析。
"""

from __future__ import annotations


def compare_with_mocap() -> None:
    """预留入口：未来生成 prediction-vs-mocap 离线报告。"""
    raise NotImplementedError("Mocap comparison reports are not implemented yet.")
