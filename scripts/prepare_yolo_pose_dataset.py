"""将多个 auto_labels 目录整理为 Ultralytics Pose 数据集。"""

from __future__ import annotations

import argparse
import json
import random
import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp"}
GENERATED_RELATIVE_PATHS = (
    Path("images") / "train",
    Path("images") / "val",
    Path("labels") / "train",
    Path("labels") / "val",
    Path("dataset.yaml"),
    Path("split_summary.json"),
)


@dataclass(frozen=True)
class SampleItem:
    """合并数据集时的一对图片/标签及其唯一输出名。"""

    session: str
    unique_stem: str
    image_path: Path
    label_path: Path


def parse_args() -> argparse.Namespace:
    """定义数据集整理参数，支持传入多个 auto_labels session。"""
    parser = argparse.ArgumentParser(description="Prepare a YOLO pose dataset from one or more auto-generated label directories.")
    parser.add_argument(
        "--auto-label-dir",
        required=True,
        action="append",
        help="Directory produced by generate_mocap_labels.py. Can be passed multiple times.",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output dataset directory. Defaults to outputs/datasets/<auto-label-dir-name> for one session or outputs/datasets/merged_<N>sessions for multiple sessions.",
    )
    parser.add_argument("--val-ratio", type=float, default=0.1, help="Validation split ratio.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic split.")
    parser.add_argument("--class-name", default="car_model", help="Single-class dataset name.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Remove existing generated images/labels and summary files in --out-dir before writing.",
    )
    return parser.parse_args()


def _default_out_dir(auto_label_dirs: list[Path]) -> Path:
    """根据 session 数量生成默认输出目录名。"""
    if len(auto_label_dirs) == 1:
        return auto_label_dirs[0].parents[1] / "datasets" / auto_label_dirs[0].name
    return auto_label_dirs[0].parents[1] / "datasets" / f"merged_{len(auto_label_dirs)}sessions"


def _read_image_map(auto_label_dir: Path) -> dict[str, Path]:
    """建立 label stem 到源图片路径的映射。"""
    mapping: dict[str, Path] = {}

    image_list_path = auto_label_dir / "images.txt"
    if image_list_path.exists():
        # 新版自动标注会写 images.txt，优先信任这个精确清单。
        for line in image_list_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            image_path = Path(line)
            mapping[image_path.stem] = image_path

    capture_images_dir = auto_label_dir.parents[1] / "object_capture" / auto_label_dir.name / "images"
    if capture_images_dir.exists():
        # 兼容旧输出：没有 images.txt 时，从 object_capture/session/images 反查。
        for image_path in sorted(capture_images_dir.iterdir()):
            if image_path.is_file() and image_path.suffix.lower() in IMAGE_SUFFIXES:
                mapping.setdefault(image_path.stem, image_path)

    if not mapping:
        raise FileNotFoundError(
            f"Could not build an image map for {auto_label_dir}. Checked images.txt and {capture_images_dir}"
        )
    return mapping


def _infer_num_keypoints(label_path: Path) -> int:
    """从第一行 YOLO Pose 标签中推断关键点数量。"""
    first = label_path.read_text(encoding="utf-8").strip().split()
    if len(first) < 8:
        raise RuntimeError(f"Label file has too few columns: {label_path}")
    remainder = len(first) - 5
    if remainder % 3 != 0:
        raise RuntimeError(f"Label format is not YOLO pose-compatible: {label_path}")
    return remainder // 3


def _collect_samples(auto_label_dirs: list[Path]) -> tuple[list[SampleItem], int, dict[str, int]]:
    """收集所有 session 的图片/标签，并检查关键点数与文件完整性。"""
    items: list[SampleItem] = []
    per_session_counts: dict[str, int] = {}
    num_keypoints: int | None = None
    seen_stems: set[str] = set()

    for auto_label_dir in auto_label_dirs:
        session = auto_label_dir.name
        labels_src = auto_label_dir / "labels_yolo_pose"
        if not labels_src.exists():
            raise FileNotFoundError(f"Missing labels_yolo_pose in {auto_label_dir}")

        image_map = _read_image_map(auto_label_dir)
        label_files = sorted(labels_src.glob("*.txt"))
        if not label_files:
            raise RuntimeError(f"No labels found in {labels_src}")

        per_session_counts[session] = len(label_files)
        for label_path in label_files:
            stem = label_path.stem
            if stem not in image_map:
                raise RuntimeError(f"Image for label {label_path.name} was not found for session {session}")
            image_path = image_map[stem]
            if not image_path.exists():
                raise RuntimeError(f"Source image does not exist: {image_path}")
            if image_path.stat().st_size <= 0:
                raise RuntimeError(f"Source image is empty: {image_path}")
            this_num_keypoints = _infer_num_keypoints(label_path)
            if num_keypoints is None:
                num_keypoints = this_num_keypoints
            elif num_keypoints != this_num_keypoints:
                raise RuntimeError(
                    f"Inconsistent keypoint count: expected {num_keypoints}, got {this_num_keypoints} in {label_path}"
                )

            unique_stem = f"{session}__{stem}"
            if unique_stem in seen_stems:
                raise RuntimeError(f"Duplicate merged stem detected: {unique_stem}")
            # 输出文件名前加 session，避免不同 session 中 car_0001 互相覆盖。
            seen_stems.add(unique_stem)
            items.append(
                SampleItem(
                    session=session,
                    unique_stem=unique_stem,
                    image_path=image_path,
                    label_path=label_path,
                )
            )

    if num_keypoints is None:
        raise RuntimeError("No valid labels were found.")
    return items, num_keypoints, per_session_counts


def _copy_pair(item: SampleItem, images_out: Path, labels_out: Path) -> None:
    """把一对图片和标签复制到 train/val 目标目录。"""
    image_dst = images_out / f"{item.unique_stem}{item.image_path.suffix}"
    label_dst = labels_out / f"{item.unique_stem}.txt"
    shutil.copy2(item.image_path, image_dst)
    shutil.copy2(item.label_path, label_dst)


def _existing_generated_outputs(out_dir: Path) -> list[Path]:
    """检查输出目录中是否已有本脚本生成的关键产物。"""
    existing: list[Path] = []
    for relative_path in GENERATED_RELATIVE_PATHS:
        path = out_dir / relative_path
        if path.is_file():
            existing.append(path)
        elif path.is_dir() and any(path.iterdir()):
            existing.append(path)
    return existing


def _prepare_output_dir(out_dir: Path, overwrite: bool) -> None:
    """默认拒绝写入非空输出；只有显式 --overwrite 才清理旧产物。"""
    existing = _existing_generated_outputs(out_dir)
    if existing and not overwrite:
        formatted = "\n".join(f"  - {path}" for path in existing)
        raise RuntimeError(
            "Output directory already contains generated dataset files. "
            "Use --overwrite to rebuild it after checking the path.\n"
            f"{formatted}"
        )

    if overwrite:
        for relative_path in GENERATED_RELATIVE_PATHS:
            # 只删除本脚本负责生成的目录/文件，避免误删同级的其他实验资产。
            path = out_dir / relative_path
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()


def main() -> None:
    """合并多个 auto_labels 目录，生成 Ultralytics Pose 数据集结构。"""
    args = parse_args()
    auto_label_dirs = [Path(path).resolve() for path in args.auto_label_dir]
    out_dir = Path(args.out_dir).resolve() if args.out_dir else _default_out_dir(auto_label_dirs)

    items, num_keypoints, per_session_counts = _collect_samples(auto_label_dirs)
    _prepare_output_dir(out_dir, overwrite=args.overwrite)

    rng = random.Random(args.seed)
    shuffled = items[:]
    # 固定 seed 后随机划分，保证同样输入能复现 train/val split。
    rng.shuffle(shuffled)

    val_count = max(1, int(round(len(shuffled) * args.val_ratio))) if len(shuffled) > 1 else 0
    val_items = shuffled[:val_count]
    train_items = shuffled[val_count:]

    images_train = out_dir / "images" / "train"
    images_val = out_dir / "images" / "val"
    labels_train = out_dir / "labels" / "train"
    labels_val = out_dir / "labels" / "val"
    for directory in (images_train, images_val, labels_train, labels_val):
        directory.mkdir(parents=True, exist_ok=True)

    for item in train_items:
        _copy_pair(item, images_train, labels_train)
    for item in val_items:
        _copy_pair(item, images_val, labels_val)

    dataset_yaml = {
        "path": out_dir.as_posix(),
        "train": "images/train",
        "val": "images/val",
        "nc": 1,
        "names": [args.class_name],
        "kpt_shape": [num_keypoints, 3],
    }
    (out_dir / "dataset.yaml").write_text(yaml.safe_dump(dataset_yaml, allow_unicode=True, sort_keys=False), encoding="utf-8")

    summary = {
        "auto_label_dirs": [str(path) for path in auto_label_dirs],
        "dataset_dir": str(out_dir),
        "num_total": len(items),
        "num_train": len(train_items),
        "num_val": len(val_items),
        "num_keypoints": num_keypoints,
        "class_name": args.class_name,
        "seed": args.seed,
        "val_ratio": args.val_ratio,
        "per_session_counts": per_session_counts,
    }
    (out_dir / "split_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()


