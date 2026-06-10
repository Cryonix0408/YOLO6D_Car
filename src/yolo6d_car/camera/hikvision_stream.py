"""将现有 HikvisionCamera 适配为项目统一相机接口。"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import warnings

import numpy as np
import yaml

from .base_camera import BaseCamera, CameraFrame
from .hikvision_camera import HikvisionCamera
from ..types import CameraIntrinsics


def _load_intrinsics(path: str | Path | None, width: int, height: int) -> CameraIntrinsics:
    """读取标定内参；未提供时给出近似值，仅保证采集流程可运行。"""
    if path:
        intrinsics_path = Path(path).expanduser()
        if intrinsics_path.exists():
            raw = yaml.safe_load(intrinsics_path.read_text(encoding="utf-8")) or {}
            matrix = raw.get("camera_matrix", {})
            distortion = raw.get("distortion", {})
            return CameraIntrinsics(
                fx=float(matrix["fx"]),
                fy=float(matrix["fy"]),
                cx=float(matrix["cx"]),
                cy=float(matrix["cy"]),
                width=int(raw.get("camera", {}).get("width", width)),
                height=int(raw.get("camera", {}).get("height", height)),
                dist_coeffs=np.asarray(distortion.get("vector", [0, 0, 0, 0, 0]), dtype=np.float64),
            )
    warnings.warn("Hikrobot 未加载真实内参；可以采集图像，但不可据此进行高精度 PnP。", RuntimeWarning)
    focal = float(max(width, height))
    return CameraIntrinsics(focal, focal, width / 2.0, height / 2.0, width, height, np.zeros(5, dtype=np.float64))


class HikvisionStream(BaseCamera):
    """复用底层 MVS 后端并输出统一 CameraFrame。"""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.width = int(config.get("width", config.get("color_width", 1440)))
        self.height = int(config.get("height", config.get("color_height", 1080)))
        self.lens = str(config.get("lens", "unknown"))
        self._intrinsics = _load_intrinsics(config.get("intrinsics_path"), self.width, self.height)
        self._camera = HikvisionCamera(
            device_index=int(config.get("device_index", 0)),
            exposure_time_us=config.get("exposure_time_us", config.get("exposure_us")),
            exposure_auto=config.get("exposure_auto", "continuous"),
            auto_exposure_upper_us=config.get("auto_exposure_upper_us"),
            gain_db=config.get("gain_db", config.get("gain")),
            gain_auto=config.get("gain_auto", "continuous"),
            auto_gain_upper_db=config.get("auto_gain_upper_db"),
            frame_rate=float(config.get("frame_rate", config.get("fps", 30))),
            width=self.width,
            height=self.height,
            gamma=config.get("gamma"),
            pixel_format=config.get("pixel_format"),
            grab_timeout_ms=int(config.get("grab_timeout_ms", 1000)),
            mvs_python_path=config.get("mvs_python_path"),
        )

    @classmethod
    def validate_config(cls, config: dict[str, Any]) -> list[str]:
        warnings_out: list[str] = []
        lens = str(config.get("lens", "")).lower()
        if lens not in {"6mm", "8mm"}:
            warnings_out.append("Hikrobot 建议明确设置 lens: 6mm 或 8mm。")
        intrinsics_path = config.get("intrinsics_path")
        if not intrinsics_path:
            warnings_out.append("Hikrobot 未配置 intrinsics_path；采集可运行，但后续 PnP 不应使用近似内参。")
        elif not Path(str(intrinsics_path)).expanduser().exists():
            warnings_out.append(f"Hikrobot 内参文件当前不存在：{intrinsics_path}")
        if config.get("white_balance") is not None:
            warnings_out.append("white_balance 已保留在配置中，当前底层后端尚未显式应用该字段。")
        if str(config.get("trigger_mode", "off")).lower() not in {"off", "false", "0"}:
            warnings_out.append("当前后端默认关闭硬触发；非 off trigger_mode 仍需真实硬件验证。")
        return warnings_out

    def open(self) -> None:
        self._camera.open()

    def start(self) -> None:
        self._camera.open()
        self._camera.start()

    def close(self) -> None:
        self._camera.close()

    def stop(self) -> None:
        self._camera.stop()
        self._camera.close()

    def is_opened(self) -> bool:
        return bool(self._camera._is_open)

    def read(self) -> CameraFrame:
        frame_id, timestamp, image = self._camera.get_frame()
        return CameraFrame(
            rgb=image,
            depth=None,
            timestamp=timestamp,
            frame_id=frame_id,
            camera_type="hikrobot",
            lens=self.lens,
            intrinsics=self._intrinsics,
            metadata={
                "pixel_format": self._camera.last_pixel_type_name,
                "exposure_time_us": self._camera.last_exposure_time_us,
                "gain_db": self._camera.last_gain_db,
            },
        )

    def get_intrinsics(self) -> CameraIntrinsics:
        return self._intrinsics

    def get_camera_info(self) -> dict[str, Any]:
        return {"camera_type": "hikrobot", "lens": self.lens, "width": self.width, "height": self.height}
