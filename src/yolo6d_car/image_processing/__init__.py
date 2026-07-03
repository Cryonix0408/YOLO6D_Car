"""图像离线处理工具。

本包中的功能默认不接入正式采集和推理流程，便于先独立验证算法效果。
"""

from .color_correction import (
    apply_ccm,
    apply_gamma_correction,
    apply_hsv_v_enhancement,
    apply_rgb_channel_gain,
    compute_color_error,
    compute_roi_mean_colors,
    estimate_ccm_least_squares,
    estimate_rgb_channel_gain,
    load_image,
    make_comparison_canvas,
    parse_roi_config,
    save_image,
)

__all__ = [
    "apply_ccm",
    "apply_gamma_correction",
    "apply_hsv_v_enhancement",
    "apply_rgb_channel_gain",
    "compute_color_error",
    "compute_roi_mean_colors",
    "estimate_ccm_least_squares",
    "estimate_rgb_channel_gain",
    "load_image",
    "make_comparison_canvas",
    "parse_roi_config",
    "save_image",
]
