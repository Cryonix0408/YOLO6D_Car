"""统一相机接口和帧数据结构。

统一接口让采集、推理和质量检查代码不需要知道图像来自 D455、Hikrobot
还是普通 USB 摄像头。真实硬件 SDK 仍由各自后端负责。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..types import CameraIntrinsics, ImageFrame


@dataclass(slots=True)
class CameraFrame:
    """统一表示相机输出的一帧数据。"""

    rgb: np.ndarray
    depth: np.ndarray | None
    timestamp: float
    frame_id: int
    camera_type: str
    lens: str | None
    intrinsics: CameraIntrinsics
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def color(self) -> np.ndarray:
        """兼容旧代码使用的 frame.color。"""
        return self.rgb

    @property
    def timestamp_s(self) -> float:
        """兼容旧代码使用的 frame.timestamp_s。"""
        return self.timestamp

    def to_image_frame(self) -> ImageFrame:
        """转换为旧 Pipeline 使用的 ImageFrame。"""
        return ImageFrame(self.rgb, self.depth, self.timestamp, self.intrinsics)


class BaseCamera(ABC):
    """所有相机后端共同遵循的最小接口。"""

    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def is_opened(self) -> bool: ...

    @abstractmethod
    def read(self) -> CameraFrame: ...

    @abstractmethod
    def get_intrinsics(self) -> CameraIntrinsics: ...

    @abstractmethod
    def get_camera_info(self) -> dict[str, Any]: ...

    @classmethod
    @abstractmethod
    def validate_config(cls, config: dict[str, Any]) -> list[str]:
        """只做结构检查并返回 warning，不连接真实硬件。"""

    def start(self) -> None:
        """兼容旧采集脚本的 start 接口。"""
        self.open()

    def stop(self) -> None:
        """兼容旧采集脚本的 stop 接口。"""
        self.close()

    def wait_for_frame(self) -> CameraFrame:
        """兼容旧 D455Stream 的 wait_for_frame 接口。"""
        return self.read()
