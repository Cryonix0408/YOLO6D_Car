"""本文件作用：
    管理 YOLO Pose dataset 版本。

在 YOLO6D_Car pipeline 中的位置：
    dataset 层。它把多个 session 的 auto labels 组织成 train/val/test，
    并生成 Ultralytics 可读取的 dataset.yaml。

主要输入：
    configs/dataset_manifest_template.yaml。

主要输出：
    dataset 路径解析、summary CSV、Ultralytics dataset.yaml。

注意事项：
    dataset manifest 不代表真实图片已经存在；check-files 才会检查大数据。
    session / dataset / model 三者要分开：同一批 session 可以构建多个 dataset 版本。
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import yaml

from .path_utils import LocalPaths, load_local_paths, resolve_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class DatasetManifestError(ValueError):
    """Raised when a dataset manifest is invalid."""


def load_dataset_manifest(path: str | Path, paths_config: str | Path | None = None) -> dict[str, Any]:
    """Load and structurally validate a dataset manifest YAML."""
    manifest_path = Path(path).resolve()
    if not manifest_path.exists():
        raise FileNotFoundError(f"Dataset manifest not found: {manifest_path}")
    if paths_config is not None:
        load_local_paths(paths_config)
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    validate_dataset_manifest(raw)
    return raw


def validate_dataset_manifest(manifest: dict[str, Any]) -> None:
    """Validate required fields without requiring real images or labels."""
    if not isinstance(manifest, dict):
        raise DatasetManifestError("Dataset manifest root must be a mapping.")
    dataset = _require_mapping(manifest, "dataset")
    for key in ("name", "version", "task", "keypoints", "object", "description", "data_root"):
        if dataset.get(key) in {None, ""}:
            raise DatasetManifestError(f"dataset.{key} is required.")
    if str(dataset.get("task")) != "pose":
        raise DatasetManifestError("dataset.task must be 'pose' for this YOLO Pose workflow.")

    source = _require_mapping(manifest, "source_sessions")
    if not source.get("manifest"):
        raise DatasetManifestError("source_sessions.manifest is required.")
    if not isinstance(source.get("include_splits"), list) or not source.get("include_splits"):
        raise DatasetManifestError("source_sessions.include_splits must be a non-empty list.")

    paths = _require_mapping(manifest, "paths")
    for key in (
        "dataset_root",
        "images_train",
        "images_val",
        "images_test",
        "labels_train",
        "labels_val",
        "labels_test",
        "data_yaml",
    ):
        if not paths.get(key):
            raise DatasetManifestError(f"paths.{key} is required.")

    yolo = _require_mapping(manifest, "yolo")
    for key in ("nc", "names", "kpt_shape", "flip_idx"):
        if key not in yolo:
            raise DatasetManifestError(f"yolo.{key} is required.")
    if int(yolo["nc"]) < 1:
        raise DatasetManifestError("yolo.nc must be >= 1.")
    if list(yolo["kpt_shape"]) != [int(dataset["keypoints"]), 3]:
        raise DatasetManifestError("yolo.kpt_shape must match [dataset.keypoints, 3].")

    splits = _require_mapping(manifest, "splits")
    total = float(splits.get("train_ratio", 0.0)) + float(splits.get("val_ratio", 0.0)) + float(splits.get("test_ratio", 0.0))
    if abs(total - 1.0) > 1e-6:
        raise DatasetManifestError(f"split ratios must sum to 1.0, got {total:.6f}.")


def resolve_dataset_paths(manifest: dict[str, Any], paths_config: str | Path | None = None) -> dict[str, Path | None]:
    """Resolve dataset paths to pathlib.Path objects."""
    local_paths = load_local_paths(paths_config) if paths_config is not None else None
    return {key: _resolve(value, local_paths) for key, value in manifest.get("paths", {}).items()}


def summarize_dataset_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return a compact summary for terminal output."""
    dataset = manifest.get("dataset", {})
    paths = manifest.get("paths", {})
    splits = manifest.get("splits", {})
    return {
        "dataset": dataset,
        "source_sessions": manifest.get("source_sessions", {}),
        "dataset_root": paths.get("dataset_root"),
        "data_yaml": paths.get("data_yaml"),
        "yolo": manifest.get("yolo", {}),
        "splits": splits,
    }


def export_dataset_summary(manifest: dict[str, Any], output_csv: str | Path) -> None:
    """Export one-row dataset manifest summary CSV."""
    output = Path(output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)
    dataset = manifest.get("dataset", {})
    paths = manifest.get("paths", {})
    splits = manifest.get("splits", {})
    yolo = manifest.get("yolo", {})
    row = {
        "name": dataset.get("name", ""),
        "version": dataset.get("version", ""),
        "task": dataset.get("task", ""),
        "keypoints": dataset.get("keypoints", ""),
        "object": dataset.get("object", ""),
        "dataset_root": paths.get("dataset_root", ""),
        "data_yaml": paths.get("data_yaml", ""),
        "nc": yolo.get("nc", ""),
        "kpt_shape": yolo.get("kpt_shape", ""),
        "train_ratio": splits.get("train_ratio", ""),
        "val_ratio": splits.get("val_ratio", ""),
        "test_ratio": splits.get("test_ratio", ""),
        "split_by": splits.get("split_by", ""),
        "source_manifest": manifest.get("source_sessions", {}).get("manifest", ""),
    }
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)


def generate_yolo_data_yaml(manifest: dict[str, Any], output_path: str | Path | None = None) -> Path:
    """Generate an Ultralytics-compatible YOLO Pose dataset.yaml."""
    paths = manifest.get("paths", {})
    yolo = manifest.get("yolo", {})
    target = Path(output_path or paths["data_yaml"])
    target.parent.mkdir(parents=True, exist_ok=True)
    dataset_root = str(paths["dataset_root"]).replace("\\", "/")
    payload = {
        "path": dataset_root,
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "nc": int(yolo["nc"]),
        "names": yolo["names"],
        "kpt_shape": list(yolo["kpt_shape"]),
        "flip_idx": list(yolo.get("flip_idx", [])),
    }
    target.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return target


def check_dataset_files(manifest: dict[str, Any], paths_config: str | Path | None = None) -> list[dict[str, str]]:
    """Check expected dataset directories and data YAML without requiring data in validate."""
    resolved = resolve_dataset_paths(manifest, paths_config)
    expected_dirs = {
        "dataset_root",
        "images_train",
        "images_val",
        "images_test",
        "labels_train",
        "labels_val",
        "labels_test",
    }
    findings: list[dict[str, str]] = []
    for key, path in resolved.items():
        if path is None:
            findings.append({"label": key, "path": "", "expected": "path", "status": "missing_path"})
            continue
        expected = "dir" if key in expected_dirs else "file"
        exists = path.is_dir() if expected == "dir" else path.is_file()
        findings.append({"label": key, "path": str(path), "expected": expected, "status": "ok" if exists else "missing"})
    return findings


def _resolve(raw_path: Any, local_paths: LocalPaths | None) -> Path | None:
    return resolve_path(None if raw_path is None else str(raw_path), project_root=PROJECT_ROOT, local_paths=local_paths)


def _require_mapping(mapping: dict[str, Any], key: str) -> dict[str, Any]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise DatasetManifestError(f"{key} must be a mapping.")
    return value
