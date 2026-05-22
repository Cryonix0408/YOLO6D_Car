"""自定义关键点检测后端模板。"""

from __future__ import annotations

import numpy as np

from ..types import ImageFrame, KeypointDetection
from .yolo6d_interface import YOLO6DBackend


class CustomYOLO6DBackend(YOLO6DBackend):
    """Template backend for integrating your real YOLO6D model.

    Replace the body of `predict` with your own inference code.
    The return value must be a list of KeypointDetection objects whose
    2D keypoint order matches the 3D keypoint order in object_model.py.
    """

    def __init__(self, model_path: str) -> None:
        self.model_path = model_path
        # TODO: load your PyTorch / ONNX / TensorRT model here.

    def predict(self, frame: ImageFrame, frame_index: int) -> list[KeypointDetection]:
        image_bgr = frame.color

        # TODO: run your network here and parse its outputs.
        # Example output shape for one detection:
        # image_points_px = np.array([
        #     [u0, v0],
        #     [u1, v1],
        #     ...
        # ], dtype=np.float64)

        _ = image_bgr, frame_index
        return [
            KeypointDetection(
                label="car_model",
                confidence=0.0,
                image_points_px=np.zeros((9, 2), dtype=np.float64),
                keypoint_scores=np.zeros(9, dtype=np.float64),
            )
        ]

