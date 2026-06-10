"""OpenCV Webcam 后端，主要用于无工业相机时的接口联调。"""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from .base_camera import BaseCamera, CameraFrame
from ..types import CameraIntrinsics


class WebcamCamera(BaseCamera):
    """通过 OpenCV VideoCapture 输出统一 CameraFrame。"""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.width = int(config.get("width", config.get("color_width", 1280)))
        self.height = int(config.get("height", config.get("color_height", 720)))
        self.fps = int(config.get("fps", 30))
        self.device_index = int(config.get("device_index", 0))
        self.lens = str(config.get("lens", "unknown"))
        self._capture = None
        self._frame_id = 0
        self._intrinsics = CameraIntrinsics(
            fx=float(config.get("fx", 900.0)),
            fy=float(config.get("fy", 900.0)),
            cx=float(config.get("cx", self.width / 2.0)),
            cy=float(config.get("cy", self.height / 2.0)),
            width=self.width,
            height=self.height,
            dist_coeffs=np.asarray(config.get("dist_coeffs", [0, 0, 0, 0, 0]), dtype=np.float64),
        )

    @classmethod
    def validate_config(cls, config: dict[str, Any]) -> list[str]:
        warnings: list[str] = []
        if not all(key in config for key in ("fx", "fy", "cx", "cy")):
            warnings.append("Webcam 未提供真实内参，当前将使用近似内参，只适合接口测试。")
        return warnings

    def open(self) -> None:
        import cv2

        if self.is_opened():
            return
        self._capture = cv2.VideoCapture(self.device_index)
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._capture.set(cv2.CAP_PROP_FPS, self.fps)
        if not self._capture.isOpened():
            self.close()
            raise RuntimeError("OpenCV webcam 打开失败。")

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def is_opened(self) -> bool:
        return self._capture is not None and bool(self._capture.isOpened())

    def read(self) -> CameraFrame:
        if not self.is_opened():
            raise RuntimeError("必须先打开 Webcam。")
        ok, image = self._capture.read()
        if not ok or image is None:
            raise RuntimeError("Webcam 未返回图像。")
        self._frame_id += 1
        return CameraFrame(
            image, None, time.perf_counter(), self._frame_id, "webcam", self.lens,
            self._intrinsics, {"device_index": self.device_index},
        )

    def get_intrinsics(self) -> CameraIntrinsics:
        return self._intrinsics

    def get_camera_info(self) -> dict[str, Any]:
        return {"camera_type": "webcam", "lens": self.lens, "device_index": self.device_index}
