"""本文件作用：
    命令行管理 model registry，并打印训练命令。

在 YOLO6D_Car pipeline 中的位置：
    model 管理层。它记录 model_id、dataset、backbone、train_run、best.pt/last.pt 等元信息。

注意事项：
    print-train-command 只打印命令，不训练；planned 模型允许权重暂时不存在。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.model_registry import (
    build_train_command,
    check_model_files,
    export_model_table,
    get_model_by_id,
    load_model_registry,
    summarize_model_registry,
    validate_model_registry,
)
from yolo6d_car.path_utils import load_local_paths, resolve_path


def parse_args() -> argparse.Namespace:
    """Parse model registry CLI."""
    parser = argparse.ArgumentParser(description="Validate and operate on YOLO6D_Car model registries.")
    parser.add_argument("--registry", required=True, help="Model registry YAML.")
    parser.add_argument("--paths-config", default=None, help="Optional paths YAML, e.g. configs/paths_local.yaml.")
    parser.add_argument(
        "--action",
        required=True,
        choices=["validate", "summary", "check-files", "export-table", "print-train-command"],
    )
    parser.add_argument("--output", default=None, help="Output CSV path for export-table.")
    parser.add_argument("--model-id", default=None, help="Model id for print-train-command.")
    parser.add_argument("--python", default=sys.executable, help="Python executable for printed train command.")
    return parser.parse_args()


def resolve_cli_path(raw_path: str, paths_config: str | None) -> Path:
    """Resolve CLI path through paths_local.yaml when provided."""
    local_paths = load_local_paths(paths_config) if paths_config else None
    path = resolve_path(raw_path, project_root=ROOT, local_paths=local_paths)
    if path is None:
        raise ValueError(f"Path is required: {raw_path}")
    return path.resolve()


def powershell_command(command: list[str]) -> str:
    """Format a command as a PowerShell-friendly multi-line string."""
    if not command:
        return ""
    if len(command) == 1:
        return command[0]
    lines = [f"{command[0]} {command[1]} ^"]
    index = 2
    while index < len(command):
        if command[index].startswith("--") and index + 1 < len(command) and not command[index + 1].startswith("--"):
            lines.append(f"  {command[index]} {command[index + 1]} ^")
            index += 2
        else:
            lines.append(f"  {command[index]} ^")
            index += 1
    lines[-1] = lines[-1].removesuffix(" ^")
    return "\n".join(lines)


def main() -> None:
    """Entrypoint."""
    args = parse_args()
    registry = load_model_registry(args.registry, paths_config=args.paths_config)

    if args.action == "validate":
        validate_model_registry(registry)
        print(json.dumps({"status": "ok", "models": len(registry.get("models", []))}, ensure_ascii=False, indent=2))
        return None

    if args.action == "summary":
        print(json.dumps(summarize_model_registry(registry), ensure_ascii=False, indent=2))
        return None

    if args.action == "check-files":
        findings = check_model_files(registry, args.paths_config)
        missing = sum(1 for model in findings for item in model["findings"] if item["status"] not in {"ok", "missing_allowed"})
        print(json.dumps({"status": "ok", "missing_required": missing, "models": findings}, ensure_ascii=False, indent=2))
        return None

    if args.action == "export-table":
        if args.output is None:
            raise SystemExit("--output is required for --action export-table")
        output = resolve_cli_path(args.output, args.paths_config)
        export_model_table(registry, output)
        print(json.dumps({"status": "ok", "output": str(output)}, ensure_ascii=False, indent=2))
        return None

    if args.action == "print-train-command":
        if args.model_id is None:
            raise SystemExit("--model-id is required for --action print-train-command")
        model = get_model_by_id(registry, args.model_id)
        command = build_train_command(model, args.python, args.paths_config)
        print(powershell_command(command))
        return None

    raise SystemExit(f"Unsupported action: {args.action}")


if __name__ == "__main__":
    main()
