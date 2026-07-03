"""离线图像色彩校正算法。

OpenCV 图像统一使用 BGR 顺序；配置中的目标颜色使用 RGB 顺序。公开函数的参数名会显式
标注颜色顺序，避免在实验中把 RGB 和 BGR 混用。本模块不连接相机，也不修改正式采集流程。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import cv2
import numpy as np


ColorMap = Mapping[str, Sequence[float] | np.ndarray]


def load_image(path: str | Path) -> np.ndarray:
    """以 OpenCV BGR 顺序读取图像。"""
    image_path = Path(path)
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"无法读取图像: {image_path}")
    return image


def save_image(path: str | Path, image_bgr: np.ndarray) -> None:
    """保存 BGR 图像，并自动创建父目录。"""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), clip_uint8(image_bgr)):
        raise OSError(f"无法保存图像: {output_path}")


def parse_roi_config(config: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """解析并校验 ROI 配置，同时生成 target_bgr。"""
    raw_rois = config.get("rois")
    if not isinstance(raw_rois, Mapping) or not raw_rois:
        raise ValueError("配置必须包含非空 rois 映射。")

    parsed: dict[str, dict[str, Any]] = {}
    for name, raw in raw_rois.items():
        if not isinstance(raw, Mapping):
            raise ValueError(f"ROI '{name}' 必须是映射。")
        xywh = raw.get("xywh")
        target_rgb = raw.get("target_rgb")
        if not isinstance(xywh, Sequence) or len(xywh) != 4:
            raise ValueError(f"ROI '{name}'.xywh 必须包含 [x, y, width, height]。")
        if not isinstance(target_rgb, Sequence) or len(target_rgb) != 3:
            raise ValueError(f"ROI '{name}'.target_rgb 必须包含三个 RGB 数值。")

        x, y, width, height = (int(value) for value in xywh)
        if x < 0 or y < 0 or width <= 0 or height <= 0:
            raise ValueError(f"ROI '{name}'.xywh 必须位于非负坐标且宽高大于 0。")
        target_rgb_array = np.asarray(target_rgb, dtype=np.float64)
        if np.any((target_rgb_array < 0) | (target_rgb_array > 255)):
            raise ValueError(f"ROI '{name}'.target_rgb 必须位于 [0, 255]。")
        parsed[str(name)] = {
            "xywh": [x, y, width, height],
            "target_rgb": target_rgb_array,
            "target_bgr": target_rgb_array[::-1].copy(),
        }
    return parsed


def compute_roi_mean_colors(
    image_bgr: np.ndarray,
    rois: Mapping[str, Mapping[str, Any]],
    *,
    min_roi_area: int = 1,
) -> dict[str, np.ndarray]:
    """计算每个 ROI 的平均 BGR；越界或面积不足时抛出清晰错误。"""
    height, width = image_bgr.shape[:2]
    means: dict[str, np.ndarray] = {}
    for name, roi_config in rois.items():
        x, y, roi_width, roi_height = (int(value) for value in roi_config["xywh"])
        if x + roi_width > width or y + roi_height > height:
            raise ValueError(
                f"ROI '{name}' 越界: xywh={[x, y, roi_width, roi_height]}, "
                f"image_size={[width, height]}"
            )
        if roi_width * roi_height < min_roi_area:
            raise ValueError(f"ROI '{name}' 面积小于 min_roi_area={min_roi_area}。")
        patch = image_bgr[y : y + roi_height, x : x + roi_width]
        means[name] = patch.reshape(-1, 3).mean(axis=0, dtype=np.float64)
    return means


def apply_gamma_correction(image_bgr: np.ndarray, gamma: float) -> np.ndarray:
    """应用 Gamma 校正；gamma 小于 1 会提升中间亮度。"""
    if gamma <= 0:
        raise ValueError("gamma 必须大于 0。")
    normalized = image_bgr.astype(np.float64) / 255.0
    return clip_uint8(np.power(normalized, gamma) * 255.0)


def apply_hsv_v_enhancement(image_bgr: np.ndarray, scale: float, offset: float) -> np.ndarray:
    """只调整 HSV 的 V 通道，不宣称恢复真实颜色。"""
    if scale < 0:
        raise ValueError("HSV-V scale 不能小于 0。")
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV).astype(np.float64)
    hsv[:, :, 2] = np.clip(hsv[:, :, 2] * scale + offset, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


def estimate_rgb_channel_gain(
    observed_bgr: ColorMap,
    target_bgr: ColorMap,
    *,
    min_gain: float = 0.3,
    max_gain: float = 3.0,
    epsilon: float = 1e-6,
) -> np.ndarray:
    """根据多个参考色估计 BGR 通道增益，返回顺序为 BGR。"""
    observed, target, _ = _paired_color_arrays(observed_bgr, target_bgr)
    denominator = np.maximum(observed.mean(axis=0), epsilon)
    gain_bgr = target.mean(axis=0) / denominator
    return np.clip(gain_bgr, min_gain, max_gain)


def apply_rgb_channel_gain(image_bgr: np.ndarray, gain_bgr: Sequence[float]) -> np.ndarray:
    """对 OpenCV BGR 图像应用三个通道的独立增益。"""
    gain = np.asarray(gain_bgr, dtype=np.float64).reshape(1, 1, 3)
    return clip_uint8(image_bgr.astype(np.float64) * gain)


def estimate_ccm_least_squares(
    observed_bgr: ColorMap,
    target_bgr: ColorMap,
    *,
    regularization: float = 0.0,
) -> np.ndarray:
    """使用最小二乘估计 RGB 颜色校正矩阵。

    返回矩阵满足 `corrected_rgb = observed_rgb @ ccm_rgb`。至少需要三个参考颜色。
    """
    observed_bgr_array, target_bgr_array, names = _paired_color_arrays(observed_bgr, target_bgr)
    if len(names) < 3:
        raise ValueError("估计 3x3 CCM 至少需要三个参考颜色。")
    observed_rgb = observed_bgr_array[:, ::-1]
    target_rgb = target_bgr_array[:, ::-1]
    if regularization < 0:
        raise ValueError("CCM regularization 不能小于 0。")
    if regularization > 0:
        identity = np.eye(3, dtype=np.float64)
        observed_rgb = np.vstack([observed_rgb, np.sqrt(regularization) * identity])
        target_rgb = np.vstack([target_rgb, np.sqrt(regularization) * identity])
    ccm_rgb, _, _, _ = np.linalg.lstsq(observed_rgb, target_rgb, rcond=None)
    return ccm_rgb


def apply_ccm(image_bgr: np.ndarray, ccm_rgb: np.ndarray) -> np.ndarray:
    """把 RGB CCM 应用于 BGR 图像，返回 BGR 图像。"""
    matrix = np.asarray(ccm_rgb, dtype=np.float64).reshape(3, 3)
    image_rgb = image_bgr[:, :, ::-1].astype(np.float64)
    corrected_rgb = image_rgb @ matrix
    return clip_uint8(corrected_rgb[:, :, ::-1])


def clip_uint8(image: np.ndarray) -> np.ndarray:
    """裁剪到 uint8 图像范围。"""
    return np.clip(np.asarray(image), 0, 255).astype(np.uint8)


def make_comparison_canvas(
    images_bgr: Sequence[np.ndarray],
    labels: Sequence[str],
    *,
    max_cell_width: int = 640,
) -> np.ndarray:
    """横向拼接多个结果并添加标签。"""
    if not images_bgr or len(images_bgr) != len(labels):
        raise ValueError("images_bgr 和 labels 必须非空且长度一致。")
    cells: list[np.ndarray] = []
    for image, label in zip(images_bgr, labels):
        cell = clip_uint8(image).copy()
        if cell.shape[1] > max_cell_width:
            scale = max_cell_width / cell.shape[1]
            cell = cv2.resize(cell, (max_cell_width, max(1, int(cell.shape[0] * scale))))
        cv2.rectangle(cell, (0, 0), (cell.shape[1], 42), (0, 0, 0), -1)
        cv2.putText(cell, label, (12, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 255), 2)
        cells.append(cell)
    target_height = max(cell.shape[0] for cell in cells)
    padded = [
        cv2.copyMakeBorder(cell, 0, target_height - cell.shape[0], 0, 0, cv2.BORDER_CONSTANT)
        for cell in cells
    ]
    return np.hstack(padded)


def compute_color_error(observed: Sequence[float], target: Sequence[float]) -> float:
    """计算两个三通道颜色向量的 L2 误差。"""
    return float(np.linalg.norm(np.asarray(observed, dtype=np.float64) - np.asarray(target, dtype=np.float64)))


def summarize_color_correction_result(
    before_bgr: ColorMap,
    after_bgr: ColorMap,
    target_bgr: ColorMap,
) -> list[dict[str, Any]]:
    """汇总每个参考色校正前后的 RGB 误差。"""
    rows: list[dict[str, Any]] = []
    for name in before_bgr:
        before_rgb = np.asarray(before_bgr[name], dtype=np.float64)[::-1]
        after_rgb = np.asarray(after_bgr[name], dtype=np.float64)[::-1]
        target_rgb = np.asarray(target_bgr[name], dtype=np.float64)[::-1]
        error_before = compute_color_error(before_rgb, target_rgb)
        error_after = compute_color_error(after_rgb, target_rgb)
        reduction = 0.0 if error_before <= 1e-9 else (error_before - error_after) / error_before * 100.0
        rows.append(
            {
                "color": name,
                "observed_rgb_before": before_rgb.tolist(),
                "target_rgb": target_rgb.tolist(),
                "corrected_rgb_after": after_rgb.tolist(),
                "error_before_l2": error_before,
                "error_after_l2": error_after,
                "error_reduction_percent": reduction,
            }
        )
    return rows


def _paired_color_arrays(
    observed_bgr: ColorMap,
    target_bgr: ColorMap,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    names = list(observed_bgr)
    missing = [name for name in names if name not in target_bgr]
    if missing:
        raise ValueError(f"目标颜色缺少参考项: {missing}")
    if not names:
        raise ValueError("参考颜色不能为空。")
    observed = np.vstack([np.asarray(observed_bgr[name], dtype=np.float64).reshape(3) for name in names])
    target = np.vstack([np.asarray(target_bgr[name], dtype=np.float64).reshape(3) for name in names])
    return observed, target, names
