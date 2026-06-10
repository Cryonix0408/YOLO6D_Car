"""相机接入模块：保留旧后端，并提供统一相机接口。"""

from .base_camera import BaseCamera, CameraFrame
from .d455 import D455Stream
from .factory import create_camera, validate_camera_config
from .hikvision_camera import HikvisionCamera
from .hikvision_stream import HikvisionStream
from .webcam import WebcamCamera

__all__ = [
    "BaseCamera",
    "CameraFrame",
    "D455Stream",
    "HikvisionCamera",
    "HikvisionStream",
    "WebcamCamera",
    "create_camera",
    "validate_camera_config",
]
