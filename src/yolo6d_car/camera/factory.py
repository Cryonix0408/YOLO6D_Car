"""根据配置创建统一相机后端，不连接真实硬件进行结构验证。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base_camera import BaseCamera, CameraFrame
from .d455 import D455Stream
from .hikvision_stream import HikvisionStream
from .webcam import WebcamCamera
from ..config import CameraConfig
from ..path_utils import LocalPaths, resolve_path
from ..types import CameraIntrinsics


class D455CameraAdapter(BaseCamera):
    """为旧 D455Stream 增加统一接口，同时保留旧类和旧调用方式。"""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.lens = str(config.get("lens", "integrated"))
        self._stream = D455Stream(
            CameraConfig(
                source="d455",
                color_width=int(config.get("width", config.get("color_width", 1280))),
                color_height=int(config.get("height", config.get("color_height", 720))),
                fps=int(config.get("fps", 15)),
                enable_depth=bool(config.get("enable_depth", False)),
                align_depth_to_color=bool(config.get("align_depth_to_color", False)),
            )
        )
        self._frame_id = 0

    @classmethod
    def validate_config(cls, config: dict[str, Any]) -> list[str]:
        if bool(config.get("align_depth_to_color", False)) and not bool(config.get("enable_depth", False)):
            return ["D455 已请求 align_depth_to_color，但 enable_depth=false，对齐设置不会生效。"]
        return []

    def open(self) -> None:
        return None

    def start(self) -> None:
        self._stream.start()

    def close(self) -> None:
        self._stream.stop()

    def stop(self) -> None:
        self._stream.stop()

    def is_opened(self) -> bool:
        return self._stream._pipeline is not None

    def read(self) -> CameraFrame:
        frame = self._stream.wait_for_frame()
        self._frame_id += 1
        return CameraFrame(
            frame.color, frame.depth, frame.timestamp_s, self._frame_id, "d455", self.lens,
            frame.intrinsics, {"align_depth_to_color": bool(self.config.get("align_depth_to_color", False))},
        )

    def get_intrinsics(self) -> CameraIntrinsics:
        if self._stream._intrinsics is None:
            raise RuntimeError("D455 启动后才能读取内参。")
        return self._stream._intrinsics

    def get_camera_info(self) -> dict[str, Any]:
        return {"camera_type": "d455", "lens": self.lens}


def normalize_source(source: str) -> str:
    """统一相机来源别名。"""
    value = source.strip().lower()
    return {"realsense": "d455", "hikvision": "hikrobot", "hikvision_mvs": "hikrobot"}.get(value, value)


def resolve_camera_config_paths(
    config: dict[str, Any],
    *,
    project_root: Path,
    local_paths: LocalPaths | None = None,
) -> dict[str, Any]:
    """解析相机配置中的文件路径，同时保留旧绝对路径兼容性。

    推荐在 YAML 中把 Hikrobot 内参写成 ``outputs/calibration/...``。传入
    ``paths-config`` 后，该相对路径会跟随当前机器的 ``outputs_root``；
    已有 Windows/POSIX 绝对路径则由 ``resolve_path`` 原样保留。
    """
    resolved = dict(config)
    intrinsics_path = resolve_path(
        config.get("intrinsics_path"),
        project_root=project_root,
        local_paths=local_paths,
    )
    if intrinsics_path is not None:
        # 配置字典会进入 validate JSON，因此保存为可序列化字符串。
        resolved["intrinsics_path"] = str(intrinsics_path)
    return resolved


def validate_camera_config(config: dict[str, Any]) -> list[str]:
    """只检查配置结构，不导入 SDK、不枚举设备。"""
    source = normalize_source(str(config.get("source", config.get("backend", ""))))
    camera_types = {"d455": D455CameraAdapter, "hikrobot": HikvisionStream, "webcam": WebcamCamera}
    if source not in camera_types:
        raise ValueError(f"不支持的 camera.source/backend：{source!r}")
    return camera_types[source].validate_config(config)


def create_camera(config: dict[str, Any]) -> BaseCamera:
    """根据 camera 配置创建后端；创建对象本身不会打开真实相机。"""
    source = normalize_source(str(config.get("source", config.get("backend", ""))))
    camera_types = {"d455": D455CameraAdapter, "hikrobot": HikvisionStream, "webcam": WebcamCamera}
    if source not in camera_types:
        raise ValueError(f"不支持的 camera.source/backend：{source!r}")
    return camera_types[source](config)
