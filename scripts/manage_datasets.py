"""本文件作用：
    命令行管理 dataset manifest，并生成 Ultralytics YOLO Pose dataset.yaml。

在 YOLO6D_Car pipeline 中的位置：
    dataset preparation 管理层。它不负责训练，只负责把数据集版本描述清楚。

注意事项：
    generate-data-yaml 会写 dataset.yaml；真实图片/标签缺失时，check-files 会提示但不会自动生成数据。
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.dataset_manifest import (
    check_dataset_files,
    export_dataset_summary,
    generate_yolo_data_yaml,
    load_dataset_manifest,
    resolve_dataset_paths,
    summarize_dataset_manifest,
    validate_dataset_manifest,
)
from yolo6d_car.path_utils import load_local_paths, resolve_path


def parse_args() -> argparse.Namespace:
    """Parse dataset management CLI."""
    parser = argparse.ArgumentParser(description="Validate and operate on YOLO6D_Car dataset manifests.")
    parser.add_argument("--manifest", required=True, help="Dataset manifest YAML.")
    parser.add_argument("--paths-config", default=None, help="Optional paths YAML, e.g. configs/paths_local.yaml.")
    parser.add_argument(
        "--action",
        required=True,
        choices=["validate", "summary", "generate-data-yaml", "check-files", "export-table"],
    )
    parser.add_argument("--output", default=None, help="Output path for export-table or generate-data-yaml override.")
    return parser.parse_args()


def resolve_cli_path(raw_path: str, paths_config: str | None) -> Path:
    """Resolve CLI path through paths_local.yaml when provided."""
    local_paths = load_local_paths(paths_config) if paths_config else None
    path = resolve_path(raw_path, project_root=ROOT, local_paths=local_paths)
    if path is None:
        raise ValueError(f"Path is required: {raw_path}")
    return path.resolve()


def main() -> None:
    """Entrypoint."""
    args = parse_args()
    manifest = load_dataset_manifest(args.manifest, paths_config=args.paths_config)

    if args.action == "validate":
        validate_dataset_manifest(manifest)
        print(json.dumps({"status": "ok", "dataset": manifest["dataset"]["name"]}, ensure_ascii=False, indent=2))
        return None

    if args.action == "summary":
        print(json.dumps(summarize_dataset_manifest(manifest), ensure_ascii=False, indent=2))
        return None

    if args.action == "check-files":
        findings = check_dataset_files(manifest, args.paths_config)
        missing = sum(1 for item in findings if item["status"] != "ok")
        print(json.dumps({"status": "ok", "missing_or_unresolved": missing, "findings": findings}, ensure_ascii=False, indent=2))
        return None

    if args.action == "export-table":
        if args.output is None:
            raise SystemExit("--output is required for --action export-table")
        output = resolve_cli_path(args.output, args.paths_config)
        export_dataset_summary(manifest, output)
        print(json.dumps({"status": "ok", "output": str(output)}, ensure_ascii=False, indent=2))
        return None

    if args.action == "generate-data-yaml":
        if args.output is None:
            output = resolve_dataset_paths(manifest, args.paths_config)["data_yaml"]
        else:
            output = resolve_cli_path(args.output, args.paths_config)
        if output is None:
            raise SystemExit("Could not resolve dataset.yaml output path.")
        manifest_for_yaml = copy.deepcopy(manifest)
        resolved_paths = resolve_dataset_paths(manifest, args.paths_config)
        if resolved_paths.get("dataset_root") is not None:
            manifest_for_yaml["paths"]["dataset_root"] = str(resolved_paths["dataset_root"])
        generated = generate_yolo_data_yaml(manifest_for_yaml, output)
        print(json.dumps({"status": "ok", "data_yaml": str(generated)}, ensure_ascii=False, indent=2))
        return None

    raise SystemExit(f"Unsupported action: {args.action}")


if __name__ == "__main__":
    main()
