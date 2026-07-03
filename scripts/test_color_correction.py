"""离线测试 Hikrobot 图像的亮度增强与色彩校正方法。

该脚本只读取已有图片，不连接相机，也不接入正式采集、标定或 YOLO pipeline。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.image_processing.color_correction import (  # noqa: E402
    apply_ccm,
    apply_gamma_correction,
    apply_hsv_v_enhancement,
    apply_rgb_channel_gain,
    compute_roi_mean_colors,
    estimate_ccm_least_squares,
    estimate_rgb_channel_gain,
    load_image,
    make_comparison_canvas,
    parse_roi_config,
    save_image,
    summarize_color_correction_result,
)


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}
ALL_METHODS = ("original", "gamma", "hsv_v", "rgb_gain", "ccm")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="离线测试 Gamma、HSV-V、RGB gain 和 3x3 CCM 色彩校正。")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--input", help="单张输入图片路径。")
    source.add_argument("--input-dir", help="批量输入图片目录。")
    parser.add_argument("--output-dir", required=True, help="输出目录。")
    parser.add_argument("--config", required=True, help="色彩校正 YAML 配置。")
    parser.add_argument(
        "--methods",
        default=",".join(ALL_METHODS),
        help="逗号分隔的方法，默认 original,gamma,hsv_v,rgb_gain,ccm。",
    )
    parser.add_argument("--dry-run", action="store_true", help="只校验配置，不读取或处理图片。")
    parser.add_argument("--max-images", type=int, default=20, help="批处理最大图片数，默认 20。")
    parser.add_argument("--save-debug", action="store_true", help="保存 ROI、颜色 patch 和方法对比图。")
    return parser.parse_args()


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path).resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if config.get("image", {}).get("input_color_order") != "BGR":
        raise ValueError("当前工具要求 image.input_color_order 为 BGR。")
    parse_roi_config(config)
    return config


def parse_methods(raw: str, config: dict[str, Any]) -> list[str]:
    methods = [item.strip() for item in raw.split(",") if item.strip()]
    invalid = sorted(set(methods) - set(ALL_METHODS))
    if invalid:
        raise ValueError(f"未知 methods: {invalid}，支持: {list(ALL_METHODS)}")
    enabled = ["original"]
    for method in methods:
        if method == "original" or config.get("methods", {}).get(method, {}).get("enabled", True):
            if method not in enabled:
                enabled.append(method)
    return enabled


def find_images(args: argparse.Namespace) -> list[Path]:
    if args.input:
        path = Path(args.input).resolve()
        if not path.exists():
            raise FileNotFoundError(f"输入图片不存在: {path}")
        return [path]
    if args.input_dir:
        root = Path(args.input_dir).resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"输入目录不存在: {root}")
        return sorted(path for path in root.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)[
            : args.max_images
        ]
    raise ValueError("非 dry-run 模式必须提供 --input 或 --input-dir。")


def draw_roi_overlay(
    image_bgr: np.ndarray,
    rois: dict[str, dict[str, Any]],
    observed_bgr: dict[str, np.ndarray],
) -> np.ndarray:
    overlay = image_bgr.copy()
    colors = {"red": (0, 0, 255), "green": (0, 255, 0), "blue": (255, 0, 0)}
    for name, roi in rois.items():
        x, y, width, height = roi["xywh"]
        color = colors.get(name.lower(), (0, 255, 255))
        cv2.rectangle(overlay, (x, y), (x + width, y + height), color, 3)
        mean_bgr = observed_bgr[name]
        text = f"{name} BGR={np.round(mean_bgr, 1).tolist()}"
        cv2.putText(overlay, text, (x, max(24, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
    return overlay


def make_color_patches(
    before_bgr: dict[str, np.ndarray],
    target_bgr: dict[str, np.ndarray],
    corrected_bgr: dict[str, np.ndarray],
) -> np.ndarray:
    patch_width, patch_height = 180, 90
    canvas = np.zeros((len(before_bgr) * patch_height, patch_width * 3, 3), dtype=np.uint8)
    for row, name in enumerate(before_bgr):
        for column, (label, color) in enumerate(
            (("before", before_bgr[name]), ("target", target_bgr[name]), ("corrected", corrected_bgr[name]))
        ):
            y0, x0 = row * patch_height, column * patch_width
            canvas[y0 : y0 + patch_height, x0 : x0 + patch_width] = np.clip(color, 0, 255).astype(np.uint8)
            cv2.putText(
                canvas,
                f"{name}:{label}",
                (x0 + 5, y0 + 22),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                1,
            )
    return canvas


def apply_methods(
    image_bgr: np.ndarray,
    config: dict[str, Any],
    methods: list[str],
    observed_bgr: dict[str, np.ndarray],
    target_bgr: dict[str, np.ndarray],
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    outputs = {"original": image_bgr}
    params: dict[str, Any] = {"color_spaces": {"image": "BGR", "targets": "RGB", "ccm": "RGB"}}
    method_config = config["methods"]
    if "gamma" in methods:
        gamma = float(method_config["gamma"]["gamma"])
        outputs["gamma"] = apply_gamma_correction(image_bgr, gamma)
        params["gamma"] = {"gamma": gamma}
    if "hsv_v" in methods:
        scale = float(method_config["hsv_v"]["scale"])
        offset = float(method_config["hsv_v"]["offset"])
        outputs["hsv_v"] = apply_hsv_v_enhancement(image_bgr, scale, offset)
        params["hsv_v"] = {"scale": scale, "offset": offset}
    if "rgb_gain" in methods:
        gain_bgr = estimate_rgb_channel_gain(
            observed_bgr,
            target_bgr,
            min_gain=float(method_config["rgb_gain"].get("min_gain", 0.3)),
            max_gain=float(method_config["rgb_gain"].get("max_gain", 3.0)),
        )
        outputs["rgb_gain"] = apply_rgb_channel_gain(image_bgr, gain_bgr)
        params["rgb_gain"] = {"gain_bgr": gain_bgr.tolist(), "gain_rgb": gain_bgr[::-1].tolist()}
    if "ccm" in methods:
        ccm_rgb = estimate_ccm_least_squares(
            observed_bgr,
            target_bgr,
            regularization=float(method_config["ccm"].get("regularization", 0.0)),
        )
        outputs["ccm"] = apply_ccm(image_bgr, ccm_rgb)
        params["ccm"] = {"matrix_rgb_row_vector": ccm_rgb.tolist()}
    return {name: outputs[name] for name in methods}, params


def quality_warnings(
    observed_bgr: dict[str, np.ndarray],
    config: dict[str, Any],
) -> list[str]:
    checks = config.get("quality_checks", {})
    dark_threshold = float(checks.get("dark_threshold", 30))
    saturation_threshold = float(checks.get("saturation_threshold", 245))
    warnings: list[str] = []
    for name, color in observed_bgr.items():
        if checks.get("warn_if_roi_too_dark", True) and float(np.mean(color)) < dark_threshold:
            warnings.append(f"ROI '{name}' 过暗，均值={float(np.mean(color)):.2f}")
        if float(np.max(color)) >= saturation_threshold:
            warnings.append(f"ROI '{name}' 可能存在饱和通道，最大值={float(np.max(color)):.2f}")
    return warnings


def write_report(
    output_dir: Path,
    config_path: Path,
    image_results: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
) -> None:
    params_path = output_dir / "color_correction_params.json"
    params_path.write_text(
        json.dumps(
            {
                "config": str(config_path),
                "note": "这是离线色彩校正实验，不会增加真实进光量，也不能替代补光灯。",
                "images": image_results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    headers = [
        "image",
        "method",
        "color",
        "observed_rgb_before",
        "target_rgb",
        "corrected_rgb_after",
        "error_before_l2",
        "error_after_l2",
        "error_reduction_percent",
    ]
    with (output_dir / "color_correction_summary.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(summary_rows)

    lines = [
        "# 离线色彩校正实验报告",
        "",
        "> 本方法只校正已有像素颜色，不会增加真实进光量，不能替代补光灯。",
        "",
        f"- 配置：`{config_path}`",
        f"- 处理图片数：{len(image_results)}",
        "",
        "| image | method | color | observed before | target | corrected after | error before | error after | reduction |",
        "|---|---|---|---|---|---|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['image']} | {row['method']} | {row['color']} | "
            f"{row['observed_rgb_before']} | {row['target_rgb']} | {row['corrected_rgb_after']} | "
            f"{row['error_before_l2']:.2f} | {row['error_after_l2']:.2f} | "
            f"{row['error_reduction_percent']:.2f}% |"
        )
    lines.extend(["", "## 警告", ""])
    warnings = [warning for result in image_results for warning in result["warnings"]]
    lines.extend([f"- {warning}" for warning in warnings] or ["- 无。"])
    (output_dir / "color_correction_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    methods = parse_methods(args.methods, config)
    rois = parse_roi_config(config)
    if args.dry_run:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "mode": "dry-run",
                    "config": str(config_path),
                    "methods": methods,
                    "rois": {name: roi["xywh"] for name, roi in rois.items()},
                    "warning": "ROI 和 target_rgb 是占位值，正式实验前必须根据真实图片修改。",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    images = find_images(args)
    if not images:
        raise RuntimeError("没有找到可处理的图片。")
    output_dir = Path(args.output_dir).resolve()
    corrected_dir = output_dir / "corrected"
    debug_dir = output_dir / "debug"
    corrected_dir.mkdir(parents=True, exist_ok=True)
    if args.save_debug:
        debug_dir.mkdir(parents=True, exist_ok=True)

    min_roi_area = int(config.get("quality_checks", {}).get("min_roi_area", 1))
    target_bgr = {name: roi["target_bgr"] for name, roi in rois.items()}
    image_results: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for image_path in images:
        image_bgr = load_image(image_path)
        observed_bgr = compute_roi_mean_colors(image_bgr, rois, min_roi_area=min_roi_area)
        outputs, params = apply_methods(image_bgr, config, methods, observed_bgr, target_bgr)
        warnings = quality_warnings(observed_bgr, config)
        stem = image_path.stem
        for method, output_image in outputs.items():
            save_image(corrected_dir / f"{stem}_{method}.jpg", output_image)
            corrected_means = compute_roi_mean_colors(output_image, rois, min_roi_area=min_roi_area)
            for row in summarize_color_correction_result(observed_bgr, corrected_means, target_bgr):
                summary_rows.append({"image": image_path.name, "method": method, **row})
        if args.save_debug:
            save_image(debug_dir / f"{stem}_roi_overlay.jpg", draw_roi_overlay(image_bgr, rois, observed_bgr))
            save_image(
                debug_dir / f"{stem}_comparison_canvas.jpg",
                make_comparison_canvas(list(outputs.values()), list(outputs)),
            )
            best_method = "ccm" if "ccm" in outputs else list(outputs)[-1]
            corrected_means = compute_roi_mean_colors(outputs[best_method], rois, min_roi_area=min_roi_area)
            save_image(
                debug_dir / f"{stem}_color_patches.jpg",
                make_color_patches(observed_bgr, target_bgr, corrected_means),
            )
        image_results.append(
            {
                "image": str(image_path),
                "observed_bgr": {name: color.tolist() for name, color in observed_bgr.items()},
                "target_rgb": {name: roi["target_rgb"].tolist() for name, roi in rois.items()},
                "params": params,
                "warnings": warnings,
            }
        )
        print(f"processed: {image_path.name}")

    write_report(output_dir, config_path, image_results, summary_rows)
    print(json.dumps({"status": "ok", "images": len(images), "output_dir": str(output_dir)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
