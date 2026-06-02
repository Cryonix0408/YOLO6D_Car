"""本文件作用：
    规则型 measurement reliability estimator，用于 reliability-aware Kalman Filter。

在 YOLO6D_Car pipeline 中的位置：
    PnP 得到 raw pose 后、Kalman correct 前。它根据 confidence、reprojection_error、
    可选 blur_score、pose_jump 判断这一帧 measurement 是否可信。

主要输出：
    reliability_score: 0~1，越高表示越可信。
    dynamic_R_scale: Kalman measurement noise R 的缩放倍数，越大表示越不相信当前观测。
    valid_measurement: False 时，Kalman 只 predict，不 correct。

注意事项：
    第一版是透明规则，不是学习模型；参数主要在 configs/kalman_reliability.yaml 中调。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any

import numpy as np

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ReliabilityResult:
    """Reliability decision for one pose measurement."""

    reliability_score: float
    dynamic_R_scale: float
    valid_measurement: bool
    reject_reason: str | None
    confidence_used: float
    reprojection_error_used: float
    blur_score_used: float
    translation_jump_m: float
    rotation_jump_rad: float
    debug_info: dict[str, Any] = field(default_factory=dict)


class ReliabilityEstimator:
    """Estimate measurement quality and dynamic Kalman R scaling.

    第一版故意保持简单透明：
        confidence、reprojection_error、可选 blur、pose_jump 会转成 [0, 1] 质量分。
        质量低会增大 dynamic_R_scale；超过硬阈值时可以直接 reject measurement。
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Create an estimator from the top-level Kalman YAML mapping."""
        raw = config or {}
        self.config = raw.get("reliability", raw) if isinstance(raw.get("reliability", raw), dict) else {}
        self.enabled = bool(self.config.get("enabled", True))

    def compute_blur_score(self, frame: Any = None) -> float:
        """Compute Laplacian-variance blur score, or return the configured default."""
        blur_cfg = self._section("blur")
        default_score = float(blur_cfg.get("default_score", 120.0))
        if frame is None:
            return default_score

        image = getattr(frame, "color", frame)
        if image is None:
            return default_score
        try:
            import cv2

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if getattr(image, "ndim", 0) == 3 else image
            return float(cv2.Laplacian(gray, cv2.CV_64F).var())
        except Exception as exc:
            LOGGER.warning("Blur score unavailable; using default %.3f: %s", default_score, exc)
            return default_score

    def compute_pose_jump(self, current_pose: Any, previous_pose: Any) -> tuple[float, float]:
        """Return translation and rotation-vector jump between two 6D poses."""
        if current_pose is None or previous_pose is None:
            return 0.0, 0.0
        current = self._pose_to_vector(current_pose)
        previous = self._pose_to_vector(previous_pose)
        if current is None or previous is None:
            return 0.0, 0.0
        return float(np.linalg.norm(current[0:3] - previous[0:3])), float(np.linalg.norm(current[3:6] - previous[3:6]))

    def estimate(
        self,
        *,
        confidence: float | None = None,
        reprojection_error: float | None = None,
        blur_score: float | None = None,
        current_pose: Any = None,
        previous_pose: Any = None,
    ) -> ReliabilityResult:
        """Estimate reliability score, dynamic R scale, and gating decision.

        参数：
            confidence: YOLO/PnP measurement 置信度，缺失时用配置默认值。
            reprojection_error: PnP 重投影误差，越大越不可信。
            blur_score: 图像清晰度，可选；当前 replay 通常没有真实帧 blur。
            current_pose/previous_pose: 用来计算 pose_jump，识别异常跳变。

        返回：
            ReliabilityResult，包含是否接受 measurement、R 缩放、拒绝原因和调试值。
        """
        debug_info: dict[str, Any] = {}
        if not self.enabled:
            return ReliabilityResult(
                reliability_score=1.0,
                dynamic_R_scale=1.0,
                valid_measurement=True,
                reject_reason=None,
                confidence_used=1.0,
                reprojection_error_used=0.0,
                blur_score_used=self._default("blur", "default_score", 120.0),
                translation_jump_m=0.0,
                rotation_jump_rad=0.0,
                debug_info={"reliability_enabled": False},
            )

        confidence_used = self._value_or_default(
            confidence,
            "confidence",
            "default_confidence",
            1.0,
            "confidence",
            debug_info,
        )
        reprojection_used = self._value_or_default(
            reprojection_error,
            "reprojection_error",
            "default_px",
            0.0,
            "reprojection_error",
            debug_info,
        )
        blur_cfg = self._section("blur")
        if bool(blur_cfg.get("enabled", False)):
            blur_used = self._value_or_default(
                blur_score,
                "blur",
                "default_score",
                120.0,
                "blur_score",
                debug_info,
            )
        else:
            blur_used = self._default("blur", "default_score", 120.0)
        translation_jump_m, rotation_jump_rad = self.compute_pose_jump(current_pose, previous_pose)

        qualities: list[tuple[float, float]] = []
        reject_reason: str | None = None

        conf_cfg = self._section("confidence")
        if bool(conf_cfg.get("enabled", True)):
            min_conf = float(conf_cfg.get("min_confidence", 0.3))
            quality = self._clamp01((confidence_used - min_conf) / max(1.0 - min_conf, 1e-9))
            qualities.append((quality, float(conf_cfg.get("weight", 1.0))))
            if confidence_used < min_conf and self._gating("reject_low_confidence", True):
                reject_reason = f"low confidence ({confidence_used:.3f} < {min_conf:.3f})"

        reproj_cfg = self._section("reprojection_error")
        if bool(reproj_cfg.get("enabled", True)):
            good_px = float(reproj_cfg.get("good_px", 3.0))
            bad_px = float(reproj_cfg.get("bad_px", 8.0))
            reject_px = float(reproj_cfg.get("reject_px", 15.0))
            quality = self._decreasing_quality(reprojection_used, good_px, bad_px)
            qualities.append((quality, float(reproj_cfg.get("weight", 1.5))))
            if reject_reason is None and reprojection_used >= reject_px and self._gating("reject_high_reprojection_error", True):
                reject_reason = f"high reprojection error ({reprojection_used:.3f}px >= {reject_px:.3f}px)"

        if bool(blur_cfg.get("enabled", False)):
            good_score = float(blur_cfg.get("good_score", 120.0))
            bad_score = float(blur_cfg.get("bad_score", 60.0))
            quality = self._increasing_quality(blur_used, bad_score, good_score)
            qualities.append((quality, float(blur_cfg.get("weight", 0.5))))

        pose_jump_cfg = self._section("pose_jump")
        if bool(pose_jump_cfg.get("enabled", True)) and previous_pose is not None:
            translation_bad = float(pose_jump_cfg.get("translation_bad_m", 0.3))
            rotation_bad = float(pose_jump_cfg.get("rotation_bad_rad", 1.0))
            reject_translation = float(pose_jump_cfg.get("reject_translation_m", 0.8))
            reject_rotation = float(pose_jump_cfg.get("reject_rotation_rad", 2.5))
            translation_quality = self._decreasing_quality(translation_jump_m, 0.0, translation_bad)
            rotation_quality = self._decreasing_quality(rotation_jump_rad, 0.0, rotation_bad)
            qualities.append((min(translation_quality, rotation_quality), float(pose_jump_cfg.get("weight", 1.0))))
            if reject_reason is None and self._gating("reject_large_pose_jump", True):
                if translation_jump_m >= reject_translation:
                    reject_reason = f"large translation jump ({translation_jump_m:.3f}m >= {reject_translation:.3f}m)"
                elif rotation_jump_rad >= reject_rotation:
                    reject_reason = f"large rotation jump ({rotation_jump_rad:.3f}rad >= {reject_rotation:.3f}rad)"

        total_weight = sum(max(weight, 0.0) for _, weight in qualities)
        if total_weight <= 0.0:
            reliability_score = 1.0
        else:
            weighted_quality = sum(self._clamp01(quality) * max(weight, 0.0) for quality, weight in qualities)
            reliability_score = self._clamp01(weighted_quality / total_weight)

        dynamic_cfg = self._section("dynamic_R")
        min_scale = float(dynamic_cfg.get("min_scale", 0.5))
        max_scale = float(dynamic_cfg.get("max_scale", 50.0))
        dynamic_r_scale = self._clamp(1.0 / max(reliability_score, 1e-6), min_scale, max_scale)

        return ReliabilityResult(
            reliability_score=reliability_score,
            dynamic_R_scale=dynamic_r_scale,
            valid_measurement=reject_reason is None,
            reject_reason=reject_reason,
            confidence_used=confidence_used,
            reprojection_error_used=reprojection_used,
            blur_score_used=blur_used,
            translation_jump_m=translation_jump_m,
            rotation_jump_rad=rotation_jump_rad,
            debug_info=debug_info,
        )

    def _section(self, name: str) -> dict[str, Any]:
        section = self.config.get(name, {})
        return section if isinstance(section, dict) else {}

    def _default(self, section: str, key: str, fallback: float) -> float:
        return float(self._section(section).get(key, fallback))

    def _value_or_default(
        self,
        value: float | None,
        section: str,
        key: str,
        fallback: float,
        label: str,
        debug_info: dict[str, Any],
    ) -> float:
        if value is None or not np.isfinite(float(value)):
            default_value = self._default(section, key, fallback)
            debug_info[f"{label}_defaulted"] = True
            LOGGER.warning("Reliability field '%s' missing or invalid; using default %.3f.", label, default_value)
            return default_value
        return float(value)

    def _gating(self, name: str, fallback: bool) -> bool:
        gating = self._section("gating")
        return bool(gating.get(name, fallback))

    @staticmethod
    def _pose_to_vector(pose: Any) -> np.ndarray | None:
        try:
            arr = np.asarray(pose, dtype=np.float64).reshape(-1)
        except Exception:
            return None
        if arr.size < 6 or not np.all(np.isfinite(arr[:6])):
            return None
        return arr[:6]

    @staticmethod
    def _clamp01(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, float(value)))

    @classmethod
    def _decreasing_quality(cls, value: float, good: float, bad: float) -> float:
        if value <= good:
            return 1.0
        if value >= bad:
            return 0.0
        return cls._clamp01(1.0 - (value - good) / max(bad - good, 1e-9))

    @classmethod
    def _increasing_quality(cls, value: float, bad: float, good: float) -> float:
        if value >= good:
            return 1.0
        if value <= bad:
            return 0.0
        return cls._clamp01((value - bad) / max(good - bad, 1e-9))


def estimate_reliability(*, confidence: float | None = None, reprojection_error_px: float | None = None) -> float:
    """Backward-compatible scalar reliability helper."""
    result = ReliabilityEstimator().estimate(confidence=confidence, reprojection_error=reprojection_error_px)
    return result.reliability_score
