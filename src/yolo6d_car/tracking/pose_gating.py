"""本文件作用：
    预留的 pose gating 模块，用于未来把离群 pose 判断从 reliability_estimator 中拆出来。

在 YOLO6D_Car pipeline 中的位置：
    tracking 层。当前正式 replay 使用 reliability_estimator.py 中的规则；
    本文件只是轻量 placeholder，避免后续新增 gating 时再改包结构。

注意事项：
    目前只有 passes_basic_gate 这个最小函数，不代表完整 outlier rejection 已实现。
"""

from __future__ import annotations


def passes_basic_gate(*, reliability: float, min_reliability: float = 0.2) -> bool:
    """根据 reliability_score 做最简单的通过/拒绝判断。"""
    return float(reliability) >= float(min_reliability)
