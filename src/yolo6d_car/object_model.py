"""小车 3D 关键点模型与边连接定义。"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


# 立方体 / 长方体默认边连接顺序，便于做可视化。
CUBOID_EDGES = [
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 0),
    (4, 5),
    (5, 6),
    (6, 7),
    (7, 4),
    (0, 4),
    (1, 5),
    (2, 6),
    (3, 7),
]


def build_cuboid_keypoints(dimensions_m: tuple[float, float, float], include_center: bool = True) -> np.ndarray:
    """根据长宽高构造对称长方体关键点。"""
    length, width, height = dimensions_m
    hx = length / 2.0
    hy = width / 2.0
    hz = height / 2.0

    keypoints = np.array(
        [
            [hx, hy, hz],
            [hx, -hy, hz],
            [-hx, -hy, hz],
            [-hx, hy, hz],
            [hx, hy, -hz],
            [hx, -hy, -hz],
            [-hx, -hy, -hz],
            [-hx, hy, -hz],
        ],
        dtype=np.float64,
    )

    if include_center:
        # 中心点可作为额外关键点，但当前 12 点自定义模型默认不使用它。
        keypoints = np.vstack([keypoints, np.zeros((1, 3), dtype=np.float64)])

    return keypoints


def build_extents_cuboid_keypoints(extents_m: tuple[float, float, float, float, float, float], include_center: bool = True) -> np.ndarray:
    """根据不对称包围盒 extents 构造关键点。"""
    x_min, x_max, y_min, y_max, z_min, z_max = extents_m

    keypoints = np.array(
        [
            [x_max, y_max, z_max],
            [x_max, y_min, z_max],
            [x_min, y_min, z_max],
            [x_min, y_max, z_max],
            [x_max, y_max, z_min],
            [x_max, y_min, z_min],
            [x_min, y_min, z_min],
            [x_min, y_max, z_min],
        ],
        dtype=np.float64,
    )

    if include_center:
        # 非对称 extents 的中心不一定是原点，因此按 min/max 重新计算。
        center = np.array(
            [[(x_min + x_max) * 0.5, (y_min + y_max) * 0.5, (z_min + z_max) * 0.5]],
            dtype=np.float64,
        )
        keypoints = np.vstack([keypoints, center])

    return keypoints


def _load_custom_model(path: str | Path) -> dict:
    """读取自定义模型 JSON，并做最基本结构校验。"""
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if "points" not in payload:
        raise ValueError("Custom model JSON must contain a 'points' array.")
    return payload


def build_custom_keypoints(model_path: str | Path) -> np.ndarray:
    """从自定义模型 JSON 中读取关键点。"""
    payload = _load_custom_model(model_path)
    points = payload["points"]
    coords = [point["xyz_m"] if isinstance(point, dict) else point for point in points]
    return np.asarray(coords, dtype=np.float64).reshape(-1, 3)


def build_object_keypoints(config: dict) -> np.ndarray:
    """根据配置决定使用哪一种 3D 模型点构建方式。"""
    mode = config["keypoints_mode"].lower()
    include_center = bool(config.get("include_center", True))

    if mode == "cuboid":
        # 对称长方体：只需要长宽高。
        dimensions = tuple(float(v) for v in config["dimensions_m"])
        return build_cuboid_keypoints(dimensions, include_center=include_center)

    if mode in {"extents_cuboid", "asymmetric_cuboid"}:
        # 非对称长方体：允许模型原点不在包围盒中心。
        extents = tuple(float(v) for v in config["extents_m"])
        if len(extents) != 6:
            raise ValueError("extents_m must contain 6 values: [x_min, x_max, y_min, y_max, z_min, z_max].")
        return build_extents_cuboid_keypoints(extents, include_center=include_center)

    if mode == "custom":
        # 自定义模型从 JSON 读取，适合 marker 实测得到的 3D 点。
        model_path = config.get("model_json_path")
        if not model_path:
            raise ValueError("Custom object model requires 'model_json_path'.")
        return build_custom_keypoints(model_path)

    raise ValueError(f"Unsupported object model mode: {mode}")


def build_object_edges(config: dict) -> list[tuple[int, int]] | None:
    """根据模型类型返回用于可视化的边连接关系。"""
    mode = config["keypoints_mode"].lower()

    if mode in {"cuboid", "extents_cuboid", "asymmetric_cuboid"}:
        return list(CUBOID_EDGES)

    if mode == "custom":
        model_path = config.get("model_json_path")
        if not model_path:
            return None
        payload = _load_custom_model(model_path)
        edges = payload.get("edges")
        if edges is None:
            return None
        return [tuple(int(v) for v in edge) for edge in edges]

    return None
