"""本文件作用：
    统一处理 YOLO6D_Car 的“D 盘代码 / G 盘数据”路径规则。

在 YOLO6D_Car pipeline 中的位置：
    所有脚本读取 YAML、保存 captures、outputs、results、models 时都会间接依赖这里。

主要输入：
    configs/paths_local.yaml，以及脚本或 YAML 中写的相对路径/绝对路径。

主要输出：
    pathlib.Path 对象。相对路径会根据语义解析到 project_root 或 data_root 下。

注意事项：
    真实图片、视频、标签、训练输出和模型权重都应该落到 G 盘 data_root；
    Git 仓库只保留代码、配置、小型示例和文档，避免把大文件提交进来。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

import yaml


@dataclass(frozen=True, slots=True)
class LocalPaths:
    """Resolved local storage roots for this workstation."""

    project_root: Path
    data_root: Path
    fzmotion_root: Path
    captures_root: Path
    outputs_root: Path
    models_root: Path
    results_root: Path
    logs_root: Path


def load_local_paths(paths_config: str | Path) -> LocalPaths:
    """Load configs/paths_local.yaml and return absolute Path objects."""
    config_path = Path(paths_config).resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"Paths config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    paths_raw = raw.get("paths")
    if not isinstance(paths_raw, dict):
        raise ValueError(f"Paths config must contain a 'paths' mapping: {config_path}")

    required = (
        "project_root",
        "data_root",
        "fzmotion_root",
        "captures_root",
        "outputs_root",
        "models_root",
        "results_root",
        "logs_root",
    )
    missing = [key for key in required if not paths_raw.get(key)]
    if missing:
        raise ValueError(f"Paths config is missing required keys {missing}: {config_path}")

    return LocalPaths(**{key: Path(str(paths_raw[key])).expanduser().resolve() for key in required})


def _is_absolute_path_text(raw_path: str) -> bool:
    """Return True for Windows or POSIX absolute path strings."""
    return PureWindowsPath(raw_path).is_absolute() or PurePosixPath(raw_path).is_absolute()


def _normalize_parts(raw_path: str) -> tuple[str, ...]:
    """Split Windows/POSIX-like path text without depending on the current OS."""
    normalized = raw_path.replace("\\", "/").strip("/")
    return tuple(part for part in normalized.split("/") if part)


def resolve_path(
    raw_path: str | Path | None,
    *,
    project_root: Path,
    local_paths: LocalPaths | None = None,
) -> Path | None:
    """函数作用：
        把 YAML/CLI 里写的路径解析成绝对 Path。

    参数：
        raw_path: 原始路径，可以是 Windows 绝对路径、POSIX 风格路径或相对路径。
        project_root: 代码仓库根目录，通常是 D:/Research/YOLO6D_Car。
        local_paths: 从 paths_local.yaml 读取的 D/G 盘根目录配置。

    返回：
        解析后的 pathlib.Path；如果 raw_path 为空则返回 None。

    备注：
        outputs/、captures/、results/、FZmotion_Data/ 这类大数据路径会解析到 G 盘；
        其他普通相对路径，例如 configs/foo.yaml，会留在 project_root 下。
    """
    if raw_path is None:
        return None

    raw_text = str(raw_path).strip()
    if raw_text == "":
        return None
    if _is_absolute_path_text(raw_text):
        return Path(raw_text)

    parts = _normalize_parts(raw_text)
    if local_paths is not None and parts:
        head = parts[0]
        tail = Path(*parts[1:]) if len(parts) > 1 else Path()
        if head == "outputs":
            return local_paths.outputs_root / tail
        if head == "FZmotion_Data":
            return local_paths.fzmotion_root / tail
        if head == "captures":
            return local_paths.captures_root / tail
        if head == "results":
            return local_paths.results_root / tail
        if head == "logs":
            return local_paths.logs_root / tail
        if head == "models" and (
            str(raw_text).replace("\\", "/").startswith("models/weights")
            or Path(parts[-1]).suffix.lower() in {".pt", ".pth", ".onnx", ".engine"}
        ):
            return local_paths.models_root / tail

    return project_root / Path(*parts)


def require_existing_dir(path: Path | None, label: str) -> Path:
    """Validate that a required directory exists and return it."""
    if path is None:
        raise ValueError(f"{label} path is required")
    if not path.exists():
        raise FileNotFoundError(f"{label} directory does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"{label} is not a directory: {path}")
    return path


def require_existing_file(path: Path | None, label: str) -> Path:
    """Validate that a required file exists and return it."""
    if path is None:
        raise ValueError(f"{label} path is required")
    if not path.exists():
        raise FileNotFoundError(f"{label} file does not exist: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"{label} is not a file: {path}")
    return path
