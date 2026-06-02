"""本文件作用：
    管理 YOLO Pose 模型权重、训练 run 和模型元信息。

在 YOLO6D_Car pipeline 中的位置：
    model 层。训练完成后，best.pt/last.pt 会归档到 models/<model_id>/，
    replay/realtime 再通过 model_id 或 best_pt 找到可用模型。

主要输入：
    configs/model_registry_template.yaml。

主要输出：
    模型表、路径检查、训练命令。

注意事项：
    status=planned 时 best.pt 可以不存在；status=trained 时应存在。
    archive_train_run.py 默认不直接改 registry，是为了避免脚本自动改实验记录。
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import yaml

from .path_utils import LocalPaths, load_local_paths, resolve_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ModelRegistryError(ValueError):
    """Raised when a model registry is invalid."""


def load_model_registry(path: str | Path, paths_config: str | Path | None = None) -> dict[str, Any]:
    """Load and structurally validate a model registry YAML."""
    registry_path = Path(path).resolve()
    if not registry_path.exists():
        raise FileNotFoundError(f"Model registry not found: {registry_path}")
    if paths_config is not None:
        load_local_paths(paths_config)
    raw = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    validate_model_registry(raw)
    return raw


def validate_model_registry(registry: dict[str, Any]) -> None:
    """Validate registry fields; planned models may have missing weights."""
    if not isinstance(registry, dict):
        raise ModelRegistryError("Model registry root must be a mapping.")
    models = registry.get("models")
    if not isinstance(models, list) or not models:
        raise ModelRegistryError("Model registry must contain a non-empty 'models' list.")
    seen: set[str] = set()
    required = (
        "model_id",
        "dataset",
        "backbone",
        "train_run",
        "best_pt",
        "last_pt",
        "data_yaml",
        "image_size",
        "epochs",
        "batch",
        "status",
        "notes",
    )
    for index, model in enumerate(models):
        if not isinstance(model, dict):
            raise ModelRegistryError(f"models[{index}] must be a mapping.")
        missing = [key for key in required if key not in model]
        if missing:
            raise ModelRegistryError(f"models[{index}] missing required fields: {missing}")
        model_id = str(model.get("model_id", "")).strip()
        if not model_id:
            raise ModelRegistryError(f"models[{index}].model_id is required.")
        if model_id in seen:
            raise ModelRegistryError(f"Duplicate model_id: {model_id}")
        seen.add(model_id)
        if str(model.get("status")) not in {"planned", "training", "trained", "archived", "deprecated"}:
            raise ModelRegistryError(f"{model_id} has unsupported status: {model.get('status')}")


def resolve_model_paths(model_entry: dict[str, Any], paths_config: str | Path | None = None) -> dict[str, Path | None]:
    """Resolve model-related paths to Path objects."""
    local_paths = load_local_paths(paths_config) if paths_config is not None else None
    return {
        "train_run": _resolve(model_entry.get("train_run"), local_paths),
        "best_pt": _resolve(model_entry.get("best_pt"), local_paths),
        "last_pt": _resolve(model_entry.get("last_pt"), local_paths),
        "data_yaml": _resolve(model_entry.get("data_yaml"), local_paths),
    }


def list_models(registry: dict[str, Any]) -> list[dict[str, Any]]:
    """Return registry model entries."""
    return list(registry.get("models", []))


def get_model_by_id(registry: dict[str, Any], model_id: str) -> dict[str, Any]:
    """Return one model entry by id, or raise a clear error."""
    for model in list_models(registry):
        if str(model.get("model_id")) == str(model_id):
            return model
    raise KeyError(f"Model id not found in registry: {model_id}")


def summarize_model_registry(registry: dict[str, Any]) -> dict[str, Any]:
    """Return compact registry summary."""
    models = list_models(registry)
    return {
        "total_models": len(models),
        "models": [
            {
                "model_id": model.get("model_id"),
                "dataset": model.get("dataset"),
                "backbone": model.get("backbone"),
                "status": model.get("status"),
                "best_pt": model.get("best_pt"),
            }
            for model in models
        ],
    }


def export_model_table(registry: dict[str, Any], output_csv: str | Path) -> None:
    """Export model registry as a flat CSV table."""
    output = Path(output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "model_id",
        "dataset",
        "backbone",
        "train_run",
        "best_pt",
        "last_pt",
        "data_yaml",
        "image_size",
        "epochs",
        "batch",
        "status",
        "notes",
    ]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for model in list_models(registry):
            writer.writerow({key: model.get(key, "") for key in fields})


def check_model_files(registry: dict[str, Any], paths_config: str | Path | None = None) -> list[dict[str, Any]]:
    """Check data_yaml and weights, respecting planned/trained status."""
    payload: list[dict[str, Any]] = []
    for model in list_models(registry):
        resolved = resolve_model_paths(model, paths_config)
        findings = []
        for label, path in resolved.items():
            expected = "dir" if label == "train_run" else "file"
            required = label == "data_yaml" or str(model.get("status")) == "trained"
            if path is None:
                status = "missing_path" if required else "not_set"
            else:
                exists = path.is_dir() if expected == "dir" else path.is_file()
                status = "ok" if exists else "missing_required" if required else "missing_allowed"
            findings.append(
                {
                    "label": label,
                    "path": "" if path is None else str(path),
                    "expected": expected,
                    "required": required,
                    "status": status,
                }
            )
        payload.append({"model_id": model.get("model_id"), "status": model.get("status"), "findings": findings})
    return payload


def build_train_command(model_entry: dict[str, Any], python_exe: str, paths_config: str | None) -> list[str]:
    """Build the training command for a registry entry without executing it."""
    model_id = str(model_entry["model_id"])
    command = [
        python_exe,
        "scripts/train_ultralytics_pose.py",
    ]
    if paths_config:
        command.extend(["--paths-config", paths_config])
    command.extend(
        [
            "--dataset",
            str(model_entry["data_yaml"]),
            "--model",
            str(model_entry["backbone"]),
            "--project",
            "outputs/train_runs",
            "--name",
            model_id,
            "--epochs",
            str(model_entry["epochs"]),
            "--imgsz",
            str(model_entry["image_size"]),
            "--batch",
            str(model_entry["batch"]),
        ]
    )
    return command


def _resolve(raw_path: Any, local_paths: LocalPaths | None) -> Path | None:
    return resolve_path(None if raw_path is None else str(raw_path), project_root=PROJECT_ROOT, local_paths=local_paths)
