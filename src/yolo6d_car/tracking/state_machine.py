"""本文件作用：
    预留 tracking state machine。

在 YOLO6D_Car pipeline 中的位置：
    tracking 层。当前正式 Kalman 状态主要由 pose_kalman_filter.py 内部管理，
    包括 INIT、TRACKING、PREDICT_ONLY、LOST。

注意事项：
    本文件目前是 placeholder，只定义未来更复杂状态机可能会用到的枚举。
    不要把这里的状态和当前 CSV 中的 tracking_state 完全等同。
"""

from __future__ import annotations

from enum import Enum


class TrackingState(str, Enum):
    """未来 runtime 状态机可用的基础状态枚举。"""

    LOST = "lost"
    ACQUIRING = "acquiring"
    TRACKING = "tracking"
