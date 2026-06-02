"""本文件作用：
    将 Ultralytics 训练输出归档到统一 models/<model_id>/ 目录。

在 YOLO6D_Car pipeline 中的位置：
    training 后、replay/realtime 使用模型前。它把 best.pt、last.pt、args.yaml、
    results.csv 等从 train_run 收拢到模型版本目录。

注意事项：
    默认不覆盖已有 best.pt，也不直接修改 registry 文件；这是为了避免脚本自动改实验记录。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.model_registry import get_model_by_id, load_model_registry, resolve_model_paths
from yolo6d_car.path_utils import load_local_paths, resolve_path


def parse_args() -> argparse.Namespace:
    """Parse archive arguments."""
    parser = argparse.ArgumentParser(description="Archive best.pt/last.pt and training metadata for one model id.")
    parser.add_argument("--model-id", required=True, help="Model id in the registry.")
    parser.add_argument("--train-run", default=None, help="Ultralytics train run directory override.")
    parser.add_argument("--registry", required=True, help="Model registry YAML.")
    parser.add_argument("--paths-config", default=None, help="Optional paths YAML, e.g. configs/paths_local.yaml.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned copy operations without writing files.")
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting existing archived files.")
    return parser.parse_args()


def resolve_cli_path(raw_path: str, paths_config: str | None) -> Path:
    """Resolve CLI path through paths_local.yaml when provided."""
    local_paths = load_local_paths(paths_config) if paths_config else None
    path = resolve_path(raw_path, project_root=ROOT, local_paths=local_paths)
    if path is None:
        raise ValueError(f"Path is required: {raw_path}")
    return path.resolve()


def copy_file(src: Path, dst: Path, *, dry_run: bool, overwrite: bool) -> dict[str, str]:
    """Copy one file with no-overwrite default."""
    if not src.exists():
        return {"source": str(src), "destination": str(dst), "status": "source_missing"}
    if dst.exists() and not overwrite:
        return {"source": str(src), "destination": str(dst), "status": "destination_exists"}
    if dry_run:
        return {"source": str(src), "destination": str(dst), "status": "dry_run"}
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return {"source": str(src), "destination": str(dst), "status": "copied"}


def build_metadata(model: dict[str, Any], train_run: Path, archive_dir: Path, copies: list[dict[str, str]]) -> dict[str, Any]:
    """Build model_metadata.json payload."""
    return {
        "model_id": model["model_id"],
        "dataset": model["dataset"],
        "train_run": str(train_run),
        "archived_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "best_pt": str(archive_dir / "best.pt"),
        "last_pt": str(archive_dir / "last.pt"),
        "source_results_csv": str(train_run / "results.csv"),
        "copies": copies,
        "registry_note": "Registry file was not modified. Update status to trained after verifying archived weights.",
    }


def main() -> None:
    """Archive one train run."""
    args = parse_args()
    registry = load_model_registry(args.registry, paths_config=args.paths_config)
    model = get_model_by_id(registry, args.model_id)
    resolved = resolve_model_paths(model, args.paths_config)
    train_run = resolve_cli_path(args.train_run, args.paths_config) if args.train_run else resolved["train_run"]
    best_dst = resolved["best_pt"]
    last_dst = resolved["last_pt"]
    if train_run is None or best_dst is None or last_dst is None:
        raise SystemExit("Could not resolve train_run, best_pt, or last_pt paths.")

    archive_dir = best_dst.parent
    source_files = [
        (train_run / "weights" / "best.pt", archive_dir / "best.pt"),
        (train_run / "weights" / "last.pt", archive_dir / "last.pt"),
        (train_run / "args.yaml", archive_dir / "args.yaml"),
        (train_run / "results.csv", archive_dir / "results.csv"),
    ]
    copies = [copy_file(src, dst, dry_run=args.dry_run, overwrite=args.overwrite) for src, dst in source_files]
    metadata = build_metadata(model, train_run, archive_dir, copies)
    metadata_path = archive_dir / "model_metadata.json"
    if args.dry_run:
        metadata_status = "dry_run"
    elif metadata_path.exists() and not args.overwrite:
        metadata_status = "destination_exists"
    else:
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        metadata_status = "written"

    print(
        json.dumps(
            {
                "status": "ok",
                "dry_run": bool(args.dry_run),
                "model_id": args.model_id,
                "archive_dir": str(archive_dir),
                "copies": copies,
                "metadata_path": str(metadata_path),
                "metadata_status": metadata_status,
                "next_step": "Verify archived weights, then manually update registry status to trained.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
