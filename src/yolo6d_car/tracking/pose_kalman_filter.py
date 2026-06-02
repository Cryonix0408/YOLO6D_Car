"""本文件作用：
    Fixed constant-velocity Kalman filter for 6DoF pose replay.

在 YOLO6D_Car pipeline 中的位置：
    replay 中 PnP raw pose 之后的第一版 tracking baseline。它不替代 PnP，
    而是在 PnP 成功/失败之间提供更平滑的时序估计。

状态量：

    [px, py, pz, vx, vy, vz, rx, ry, rz, wx, wy, wz]

    p 是 translation，v 是 linear velocity，r 是 OpenCV/Rodrigues rvec，
    w 是 angular velocity。

测量量：
    [px, py, pz, rx, ry, rz]，也就是 PnP 输出的 tvec + rvec。

注意事项：
    predict-only 表示当前帧 measurement 无效或被 gating 拒绝，只用上一状态外推。
    reliability-aware KF 会临时放大/缩小 measurement noise R，但不会永久污染 base R。
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

import numpy as np
import yaml

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PoseKalmanConfig:
    """Kalman 噪声、门控和 reliability-aware 参数。

    position/rotation_process_noise 属于 Q，表示系统运动模型的不确定性；
    position/rotation_measurement_noise 属于 R，表示观测/PnP measurement 的不确定性。
    """

    enabled: bool = False
    mode: str = "fixed"
    state_dim: int = 12
    measurement_dim: int = 6
    default_fps: float = 30.0
    position_process_noise: float = 0.01
    velocity_process_noise: float = 0.1
    rotation_process_noise: float = 0.01
    angular_velocity_process_noise: float = 0.1
    position_measurement_noise: float = 0.005
    rotation_measurement_noise: float = 0.02
    max_reprojection_error_px: float = 8.0
    max_missing_frames: int = 10
    reliability_config: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class PoseKalmanResult:
    """Output of one filter update."""

    state: np.ndarray | None
    tracking_state: str
    used_measurement: bool


class PoseKalmanFilter:
    """12D constant-velocity Kalman filter with 6D pose measurements.

    fixed KF 模式：
        每帧使用固定 R。

    reliability-aware KF 模式：
        correct() 可传入 measurement_noise_scale，让低质量 measurement 的 R 变大，
        从而“少相信”这一帧观测；高质量 measurement 的 R 变小，从而“更相信”观测。
    """

    INIT = "INIT"
    TRACKING = "TRACKING"
    PREDICT_ONLY = "PREDICT_ONLY"
    LOST = "LOST"

    def __init__(self, config: PoseKalmanConfig) -> None:
        """Create an uninitialized filter from fixed noise parameters."""
        if config.state_dim != 12:
            raise ValueError(f"PoseKalmanFilter requires state_dim=12, got {config.state_dim}")
        if config.measurement_dim != 6:
            raise ValueError(f"PoseKalmanFilter requires measurement_dim=6, got {config.measurement_dim}")

        self.config = config
        self.state = np.zeros(12, dtype=np.float64)
        self.covariance = np.eye(12, dtype=np.float64)
        self.last_timestamp_s: float | None = None
        self.initialized = False
        self.missing_frames = 0
        self.tracking_state = self.INIT
        self._warned_default_dt = False
        self._measurement_noise_scale = 1.0

        self._measurement_matrix = np.zeros((6, 12), dtype=np.float64)
        self._measurement_matrix[0:3, 0:3] = np.eye(3, dtype=np.float64)
        self._measurement_matrix[3:6, 6:9] = np.eye(3, dtype=np.float64)

    def reset(self) -> None:
        """Clear filter state and require a fresh valid measurement."""
        self.state.fill(0.0)
        self.covariance = np.eye(12, dtype=np.float64)
        self.last_timestamp_s = None
        self.initialized = False
        self.missing_frames = 0
        self.tracking_state = self.INIT

    def is_initialized(self) -> bool:
        """Return whether the filter has received its first valid measurement."""
        return self.initialized

    def initialize(self, measurement: np.ndarray, timestamp: float | None = None) -> np.ndarray:
        """Initialize the filter from a 6D [translation, rvec] measurement."""
        z = np.asarray(measurement, dtype=np.float64).reshape(6)
        if not np.all(np.isfinite(z)):
            raise ValueError(f"Kalman initialization measurement contains non-finite values: {z}")

        self.state.fill(0.0)
        self.state[0:3] = z[0:3]
        self.state[6:9] = z[3:6]
        self.covariance = np.eye(12, dtype=np.float64)
        self.last_timestamp_s = None if timestamp is None else float(timestamp)
        self.initialized = True
        self.missing_frames = 0
        self.tracking_state = self.TRACKING
        return self.state.copy()

    def predict(self, timestamp: float | None = None) -> np.ndarray | None:
        """Advance the state using variable dt or ``1 / default_fps`` fallback.

        predict 只根据运动模型外推，不使用当前帧 PnP measurement。
        PnP 失败、reprojection_error 太大或 reliability gating reject 时，会走 predict-only。
        """
        if not self.initialized:
            if timestamp is not None:
                self.last_timestamp_s = float(timestamp)
            return None

        dt = self._compute_dt(timestamp)

        transition = np.eye(12, dtype=np.float64)
        transition[0:3, 3:6] = np.eye(3, dtype=np.float64) * dt
        transition[6:9, 9:12] = np.eye(3, dtype=np.float64) * dt

        self.state = transition @ self.state
        self.covariance = transition @ self.covariance @ transition.T + self._process_noise(dt)
        return self.state.copy()

    def set_measurement_noise_scale(self, scale: float) -> None:
        """Set the default measurement-noise scale for future corrections."""
        self._measurement_noise_scale = max(float(scale), 1e-9)

    def correct(
        self,
        measurement: np.ndarray,
        timestamp: float | None = None,
        measurement_noise_scale: float | None = None,
    ) -> np.ndarray:
        """Correct the predicted state with a 6D pose measurement.

        ``measurement_noise_scale`` temporarily scales the base measurement
        covariance for this correction only. It does not mutate the configured
        base R matrix, which keeps fixed-KF behavior stable.
        """
        z = np.asarray(measurement, dtype=np.float64).reshape(6)
        if not np.all(np.isfinite(z)):
            raise ValueError(f"Kalman measurement contains non-finite values: {z}")

        if not self.initialized:
            return self.initialize(z, timestamp)

        measurement_matrix = self._measurement_matrix
        residual = z - (measurement_matrix @ self.state)
        innovation_covariance = measurement_matrix @ self.covariance @ measurement_matrix.T + self._measurement_noise(
            measurement_noise_scale
        )
        kalman_gain = self.covariance @ measurement_matrix.T @ np.linalg.inv(innovation_covariance)
        self.state = self.state + kalman_gain @ residual
        identity = np.eye(12, dtype=np.float64)
        self.covariance = (identity - kalman_gain @ measurement_matrix) @ self.covariance
        self.missing_frames = 0
        self.tracking_state = self.TRACKING
        return self.state.copy()

    def update(
        self,
        measurement: np.ndarray | None,
        timestamp: float | None = None,
        *,
        valid: bool = True,
        measurement_valid: bool | None = None,
        measurement_noise_scale: float | None = None,
    ) -> PoseKalmanResult:
        """Predict then optionally correct with a valid measurement.

        If the measurement is invalid, the filter stays in predict-only mode.
        Too many consecutive missing measurements reset the filter so stale
        states are not carried indefinitely.
        """
        if measurement_valid is not None:
            valid = measurement_valid

        self.predict(timestamp)

        if valid and measurement is not None:
            state = self.correct(measurement, timestamp, measurement_noise_scale=measurement_noise_scale)
            return PoseKalmanResult(state=state, tracking_state=self.tracking_state, used_measurement=True)

        if not self.initialized:
            self.tracking_state = self.INIT
            return PoseKalmanResult(state=None, tracking_state=self.tracking_state, used_measurement=False)

        self.missing_frames += 1
        if self.missing_frames > self.config.max_missing_frames:
            self.tracking_state = self.LOST
            return PoseKalmanResult(state=self.state.copy(), tracking_state=self.tracking_state, used_measurement=False)

        self.tracking_state = self.PREDICT_ONLY
        return PoseKalmanResult(state=self.state.copy(), tracking_state=self.tracking_state, used_measurement=False)

    def get_state(self) -> np.ndarray | None:
        """Return a copy of the current 12D state, or None before initialization."""
        if not self.initialized:
            return None
        return self.state.copy()

    def get_pose(self) -> tuple[np.ndarray, np.ndarray] | None:
        """Return current filtered pose as ``(translation_m, rotation_vector)``."""
        if not self.initialized:
            return None
        return self.state[0:3].copy(), self.state[6:9].copy()

    def _compute_dt(self, timestamp: float | None) -> float:
        """Compute dt from timestamps, or fall back to the configured fixed FPS."""
        if timestamp is None:
            if not self._warned_default_dt:
                LOGGER.warning("Kalman timestamp missing; falling back to dt=1/default_fps.")
                self._warned_default_dt = True
            return 1.0 / max(float(self.config.default_fps), 1e-6)

        current = float(timestamp)
        if self.last_timestamp_s is None:
            self.last_timestamp_s = current
            return 1.0 / max(float(self.config.default_fps), 1e-6)

        dt = max(current - self.last_timestamp_s, 0.0)
        self.last_timestamp_s = current
        if dt <= 0.0:
            return 1.0 / max(float(self.config.default_fps), 1e-6)
        return dt

    def _process_noise(self, dt: float) -> np.ndarray:
        """Build a diagonal process-noise matrix scaled by the current dt."""
        scale = max(float(dt), 1e-6)
        diagonal = np.array(
            [
                self.config.position_process_noise,
                self.config.position_process_noise,
                self.config.position_process_noise,
                self.config.velocity_process_noise,
                self.config.velocity_process_noise,
                self.config.velocity_process_noise,
                self.config.rotation_process_noise,
                self.config.rotation_process_noise,
                self.config.rotation_process_noise,
                self.config.angular_velocity_process_noise,
                self.config.angular_velocity_process_noise,
                self.config.angular_velocity_process_noise,
            ],
            dtype=np.float64,
        )
        return np.diag(diagonal * scale)

    def _measurement_noise(self, scale: float | None = None) -> np.ndarray:
        """Build a diagonal measurement-noise matrix, optionally scaled."""
        noise_scale = self._measurement_noise_scale if scale is None else max(float(scale), 1e-9)
        diagonal = np.array(
            [
                self.config.position_measurement_noise,
                self.config.position_measurement_noise,
                self.config.position_measurement_noise,
                self.config.rotation_measurement_noise,
                self.config.rotation_measurement_noise,
                self.config.rotation_measurement_noise,
            ],
            dtype=np.float64,
        )
        return np.diag(diagonal * noise_scale)


def load_pose_kalman_config(config_path: str | Path) -> PoseKalmanConfig:
    """Load a YAML file containing a top-level ``kalman`` mapping."""
    path = Path(config_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Kalman config not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    kalman_raw = raw.get("kalman")
    if not isinstance(kalman_raw, dict):
        raise ValueError(f"Kalman config must contain a 'kalman' mapping: {path}")

    return PoseKalmanConfig(
        enabled=bool(kalman_raw.get("enabled", False)),
        mode=str(kalman_raw.get("mode", "fixed")),
        state_dim=int(kalman_raw.get("state_dim", 12)),
        measurement_dim=int(kalman_raw.get("measurement_dim", 6)),
        default_fps=float(kalman_raw.get("default_fps", 30.0)),
        position_process_noise=float(kalman_raw.get("position_process_noise", 0.01)),
        velocity_process_noise=float(kalman_raw.get("velocity_process_noise", 0.1)),
        rotation_process_noise=float(kalman_raw.get("rotation_process_noise", 0.01)),
        angular_velocity_process_noise=float(kalman_raw.get("angular_velocity_process_noise", 0.1)),
        position_measurement_noise=float(
            kalman_raw.get("position_measurement_noise", kalman_raw.get("base_position_measurement_noise", 0.005))
        ),
        rotation_measurement_noise=float(
            kalman_raw.get("rotation_measurement_noise", kalman_raw.get("base_rotation_measurement_noise", 0.02))
        ),
        max_reprojection_error_px=float(kalman_raw.get("max_reprojection_error_px", 8.0)),
        max_missing_frames=int(kalman_raw.get("max_missing_frames", 10)),
        reliability_config=raw.get("reliability") if isinstance(raw.get("reliability"), dict) else None,
    )
