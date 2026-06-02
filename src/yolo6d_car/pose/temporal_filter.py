"""位姿时间滤波与短时丢帧保持。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..config import TemporalFilterConfig
from ..transforms import matrix_to_quaternion, quaternion_slerp, quaternion_to_matrix, rotation_angle_deg
from ..types import PoseEstimate, PoseSE3


@dataclass(slots=True)
class TemporalFilterState:
    """保存当前滤波状态。"""

    filtered: PoseEstimate | None = None
    missed_frames: int = 0


class TemporalPoseFilter:
    """对逐帧位姿结果做平滑，并在短时丢检时保持上一帧。"""

    def __init__(self, config: TemporalFilterConfig) -> None:
        self.config = config
        self.state = TemporalFilterState()

    def reset(self) -> None:
        """清空内部状态。"""
        self.state = TemporalFilterState()

    def update(self, prediction: PoseEstimate | None) -> PoseEstimate | None:
        """输入当前帧预测，返回滤波后的位姿结果。"""
        if not self.config.enabled:
            return prediction

        if prediction is None:
            return self._handle_missing_prediction()

        filtered = self.state.filtered
        if filtered is None or self.state.missed_frames > self.config.hold_last_frames:
            self.state.filtered = self._clone_estimate(prediction)
            self.state.missed_frames = 0
            return self._clone_estimate(self.state.filtered)

        translation_jump = float(np.linalg.norm(prediction.pose.translation_m - filtered.pose.translation_m))
        angle_jump_deg = rotation_angle_deg(filtered.pose.rotation, prediction.pose.rotation)

        translation_alpha = self._effective_alpha(
            base_alpha=self.config.translation_alpha,
            jump=translation_jump,
            max_jump=self.config.max_translation_jump_m,
        )
        rotation_alpha = self._effective_alpha(
            base_alpha=self.config.rotation_alpha,
            jump=angle_jump_deg,
            max_jump=self.config.max_angle_jump_deg,
        )

        blended_pose = self._blend_pose(filtered.pose, prediction.pose, translation_alpha, rotation_alpha)
        blended_estimate = PoseEstimate(
            pose=blended_pose,
            confidence=float(prediction.confidence),
            reprojection_error_px=float(prediction.reprojection_error_px),
            num_inliers=int(prediction.num_inliers),
            detection_label=prediction.detection_label,
            source=f"{prediction.source}+temporal",
        )
        self.state.filtered = blended_estimate
        self.state.missed_frames = 0
        return self._clone_estimate(blended_estimate)

    def _handle_missing_prediction(self) -> PoseEstimate | None:
        filtered = self.state.filtered
        if filtered is None:
            return None

        self.state.missed_frames += 1
        if self.state.missed_frames > self.config.hold_last_frames:
            self.state.filtered = None
            return None

        held = self._clone_estimate(filtered)
        held.source = f"{filtered.source}+hold"
        return held

    @staticmethod
    def _clone_estimate(estimate: PoseEstimate) -> PoseEstimate:
        pose = PoseSE3(
            parent_frame=estimate.pose.parent_frame,
            child_frame=estimate.pose.child_frame,
            rotation=estimate.pose.rotation.copy(),
            translation_m=estimate.pose.translation_m.copy(),
            timestamp_s=estimate.pose.timestamp_s,
        )
        return PoseEstimate(
            pose=pose,
            confidence=float(estimate.confidence),
            reprojection_error_px=float(estimate.reprojection_error_px),
            num_inliers=int(estimate.num_inliers),
            detection_label=estimate.detection_label,
            source=estimate.source,
        )

    @staticmethod
    def _effective_alpha(base_alpha: float, jump: float, max_jump: float) -> float:
        alpha = float(np.clip(base_alpha, 0.0, 1.0))
        if max_jump <= 0.0 or jump <= max_jump:
            return alpha
        scale = max_jump / max(jump, 1e-6)
        return float(np.clip(alpha * scale, 0.05, 1.0))

    @staticmethod
    def _blend_pose(first: PoseSE3, second: PoseSE3, translation_alpha: float, rotation_alpha: float) -> PoseSE3:
        translation = (1.0 - translation_alpha) * first.translation_m + translation_alpha * second.translation_m
        q_first = matrix_to_quaternion(first.rotation)
        q_second = matrix_to_quaternion(second.rotation)
        q_blended = quaternion_slerp(q_first, q_second, rotation_alpha)
        rotation = quaternion_to_matrix(q_blended)
        return PoseSE3(
            parent_frame=second.parent_frame,
            child_frame=second.child_frame,
            rotation=rotation,
            translation_m=translation,
            timestamp_s=second.timestamp_s,
        )
