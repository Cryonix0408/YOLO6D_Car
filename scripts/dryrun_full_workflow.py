"""Dry-run the complete YOLO6D_Car workflow before real data collection."""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.dataset_manifest import check_dataset_files, load_dataset_manifest, summarize_dataset_manifest
from yolo6d_car.model_registry import (
    build_train_command,
    check_model_files,
    get_model_by_id,
    load_model_registry,
    summarize_model_registry,
)
from yolo6d_car.path_utils import load_local_paths, resolve_path
from yolo6d_car.session_manifest import check_session_files, load_session_manifest, summarize_sessions


def parse_args() -> argparse.Namespace:
    """Parse dry-run workflow arguments."""
    parser = argparse.ArgumentParser(description="Dry-run the full YOLO6D_Car workflow without real capture or training.")
    parser.add_argument("--paths-config", default="configs/paths_local.yaml")
    parser.add_argument("--session-manifest", default="configs/session_manifest_template.yaml")
    parser.add_argument("--dataset-manifest", default="configs/dataset_manifest_template.yaml")
    parser.add_argument("--model-registry", default="configs/model_registry_template.yaml")
    parser.add_argument("--model-id", default="car_pose_12pts_v1_yolov8n_pose")
    parser.add_argument("--run-name", default="full_workflow_dryrun")
    parser.add_argument("--execute-smoke-tests", action="store_true")
    parser.add_argument("--execute-ablation-smoke", action="store_true")
    parser.add_argument("--output-dir", default="results/workflow_dryruns/full_workflow_dryrun")
    parser.add_argument("--python", default=sys.executable)
    return parser.parse_args()


def resolve_cli_path(raw_path: str, paths_config: str | None) -> Path:
    """Resolve output paths through paths_local.yaml when provided."""
    local_paths = load_local_paths(paths_config) if paths_config else None
    path = resolve_path(raw_path, project_root=ROOT, local_paths=local_paths)
    if path is None:
        raise ValueError(f"Path is required: {raw_path}")
    return path.resolve()


def command_to_text(command: list[str]) -> str:
    """Format a command as PowerShell-friendly text."""
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


def run_command(command: list[str]) -> dict[str, Any]:
    """Run a command and capture stdout/stderr."""
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    return {
        "command": command,
        "returncode": completed.returncode,
        "success": completed.returncode == 0,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def import_status(module_name: str) -> dict[str, Any]:
    """Return import availability for a module."""
    try:
        module = importlib.import_module(module_name)
        return {"available": True, "version": getattr(module, "__version__", "unknown")}
    except Exception as exc:
        return {"available": False, "error": str(exc)}


def ultralytics_status() -> dict[str, Any]:
    """Import Ultralytics with a temporary config dir."""
    previous = os.environ.get("YOLO_CONFIG_DIR")
    with tempfile.TemporaryDirectory(prefix="yolo6d_ultralytics_") as tmp_dir:
        os.environ["YOLO_CONFIG_DIR"] = tmp_dir
        status = import_status("ultralytics")
    if previous is None:
        os.environ.pop("YOLO_CONFIG_DIR", None)
    else:
        os.environ["YOLO_CONFIG_DIR"] = previous
    return status


def torch_status() -> dict[str, Any]:
    """Check PyTorch/CUDA availability without allocating large tensors."""
    try:
        import torch

        cuda_available = bool(torch.cuda.is_available())
        return {
            "available": True,
            "version": torch.__version__,
            "cuda_available": cuda_available,
            "cuda_device": torch.cuda.get_device_name(0) if cuda_available else None,
        }
    except Exception as exc:
        return {"available": False, "cuda_available": False, "error": str(exc)}


def stage_row(module: str, status: str, notes: str) -> dict[str, str]:
    """Build one readiness table row."""
    return {"module": module, "status": status, "notes": notes}


def count_missing(findings: list[dict[str, Any]]) -> int:
    """Count missing file findings."""
    return sum(1 for item in findings if str(item.get("status")) not in {"ok", "missing_allowed"})


def flatten_session_findings(session_manifest: dict[str, Any], paths_config: str) -> list[dict[str, Any]]:
    """Collect check-files findings for all sessions."""
    findings: list[dict[str, Any]] = []
    for session in session_manifest.get("sessions", []):
        for item in check_session_files(session, paths_config):
            findings.append({"session_id": session.get("session_id"), **item})
    return findings


def build_commands(args: argparse.Namespace) -> dict[str, list[str]]:
    """Build all generated commands used by the report."""
    py = args.python
    return {
        "readiness check": [py, "scripts/check_project_readiness.py", "--paths-config", args.paths_config],
        "session validate": [
            py,
            "scripts/manage_sessions.py",
            "--manifest",
            args.session_manifest,
            "--paths-config",
            args.paths_config,
            "--action",
            "validate",
        ],
        "session summary": [
            py,
            "scripts/manage_sessions.py",
            "--manifest",
            args.session_manifest,
            "--paths-config",
            args.paths_config,
            "--action",
            "summary",
        ],
        "session generate replay configs": [
            py,
            "scripts/manage_sessions.py",
            "--manifest",
            args.session_manifest,
            "--paths-config",
            args.paths_config,
            "--action",
            "generate-replay-configs",
        ],
        "dataset validate": [
            py,
            "scripts/manage_datasets.py",
            "--manifest",
            args.dataset_manifest,
            "--paths-config",
            args.paths_config,
            "--action",
            "validate",
        ],
        "dataset generate data yaml": [
            py,
            "scripts/manage_datasets.py",
            "--manifest",
            args.dataset_manifest,
            "--paths-config",
            args.paths_config,
            "--action",
            "generate-data-yaml",
        ],
        "model validate": [
            py,
            "scripts/manage_models.py",
            "--registry",
            args.model_registry,
            "--paths-config",
            args.paths_config,
            "--action",
            "validate",
        ],
        "model print train command": [
            py,
            "scripts/manage_models.py",
            "--registry",
            args.model_registry,
            "--paths-config",
            args.paths_config,
            "--action",
            "print-train-command",
            "--model-id",
            args.model_id,
        ],
        "archive train run dry-run": [
            py,
            "scripts/archive_train_run.py",
            "--model-id",
            args.model_id,
            "--train-run",
            f"outputs/train_runs/{args.model_id}",
            "--registry",
            args.model_registry,
            "--paths-config",
            args.paths_config,
            "--dry-run",
        ],
        "raw replay": [
            py,
            "scripts/smoke_replay_pipeline.py",
            "--config",
            "configs/local_smoke_replay.yaml",
            "--max-frames",
            "3",
        ],
        "fixed KF replay": [
            py,
            "scripts/smoke_replay_pipeline.py",
            "--config",
            "configs/local_smoke_replay.yaml",
            "--max-frames",
            "3",
            "--kalman-config",
            "configs/kalman_fixed.yaml",
        ],
        "reliability-aware KF replay": [
            py,
            "scripts/smoke_replay_pipeline.py",
            "--config",
            "configs/local_smoke_replay.yaml",
            "--max-frames",
            "3",
            "--kalman-config",
            "configs/kalman_reliability.yaml",
        ],
        "kalman ablation": [
            py,
            "scripts/run_kalman_ablation.py",
            "--config",
            "configs/local_smoke_replay.yaml",
            "--run-name",
            args.run_name,
            "--max-frames",
            "3",
            "--plot",
        ],
    }


def write_generated_commands(path: Path, commands: dict[str, list[str]]) -> None:
    """Write generated_commands.md."""
    lines = ["# Generated Workflow Commands", ""]
    for name, command in commands.items():
        lines.extend([f"## {name}", "", "```powershell", command_to_text(command), "```", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_summary_csv(path: Path, rows: list[dict[str, str]]) -> None:
    """Write readiness table as CSV."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["module", "status", "notes"])
        writer.writeheader()
        writer.writerows(rows)


def write_report(
    path: Path,
    *,
    args: argparse.Namespace,
    local_paths,
    session_summary: dict[str, Any],
    dataset_summary: dict[str, Any],
    model_summary: dict[str, Any],
    rows: list[dict[str, str]],
    commands: dict[str, list[str]],
) -> None:
    """Write workflow_dryrun_report.md."""
    lines = [
        "# Full Workflow Dry-Run Report",
        "",
        "## Environment",
        "",
        f"- Python executable: `{sys.executable}`",
        f"- Python version: `{sys.version.split()[0]}`",
        f"- Torch/CUDA: `{torch_status()}`",
        f"- Ultralytics: `{ultralytics_status()}`",
        f"- OpenCV: `{import_status('cv2')}`",
        "",
        "## Paths",
        "",
        f"- project_root: `{local_paths.project_root}`",
        f"- data_root: `{local_paths.data_root}`",
        f"- outputs_root: `{local_paths.outputs_root}`",
        f"- models_root: `{local_paths.models_root}`",
        f"- results_root: `{local_paths.results_root}`",
        "",
        "## Manifest Summary",
        "",
        f"- Session count: {session_summary.get('total_sessions')}",
        f"- Speed levels: `{session_summary.get('by_speed_level')}`",
        f"- Camera types: `{session_summary.get('by_camera_type')}`",
        f"- Dataset version: `{dataset_summary.get('dataset', {}).get('version')}`",
        f"- Dataset name: `{dataset_summary.get('dataset', {}).get('name')}`",
        f"- Model count: {model_summary.get('total_models')}",
        "",
        "## Ready / Missing / Placeholder",
        "",
        "| Module | Status | Notes |",
        "|---|---|---|",
    ]
    for row in rows:
        lines.append(f"| {row['module']} | {row['status']} | {row['notes']} |")

    lines.extend(
        [
            "",
            "## Important Commands",
            "",
            "See `generated_commands.md` in this output directory.",
            "",
            "## Next Real Capture Checklist",
            "",
            "- Create a real `session_id`.",
            "- Confirm camera intrinsics for the exact camera/lens.",
            "- Confirm mocap rigid body names.",
            "- Capture images/videos.",
            "- Sync captures to the workstation G drive.",
            "- Place the FzMotion CSV under `FZmotion_Data`.",
            "- Update the session manifest.",
            "- Run mocap-based label generation.",
            "- Prepare the YOLO Pose dataset.",
            "- Train YOLO Pose.",
            "- Archive `best.pt`.",
            "- Run replay.",
            "- Run Kalman ablation.",
            "- Run evaluation.",
            "",
            "## Execution Flags",
            "",
            f"- execute_smoke_tests: {bool(args.execute_smoke_tests)}",
            f"- execute_ablation_smoke: {bool(args.execute_ablation_smoke)}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """Run the full workflow dry-run."""
    args = parse_args()
    local_paths = load_local_paths(args.paths_config)
    output_dir = resolve_cli_path(args.output_dir, args.paths_config)
    output_dir.mkdir(parents=True, exist_ok=True)

    session_manifest = load_session_manifest(args.session_manifest, paths_config=args.paths_config)
    dataset_manifest = load_dataset_manifest(args.dataset_manifest, paths_config=args.paths_config)
    model_registry = load_model_registry(args.model_registry, paths_config=args.paths_config)
    model_entry = get_model_by_id(model_registry, args.model_id)

    session_summary = summarize_sessions(session_manifest)
    dataset_summary = summarize_dataset_manifest(dataset_manifest)
    model_summary = summarize_model_registry(model_registry)
    commands = build_commands(args)

    session_findings = flatten_session_findings(session_manifest, args.paths_config)
    dataset_findings = check_dataset_files(dataset_manifest, args.paths_config)
    model_findings = check_model_files(model_registry, args.paths_config)

    smoke_results: dict[str, Any] = {}
    if args.execute_smoke_tests:
        for name in ("raw replay", "fixed KF replay", "reliability-aware KF replay"):
            smoke_results[name] = run_command(commands[name])
    if args.execute_ablation_smoke:
        smoke_results["kalman ablation"] = run_command(commands["kalman ablation"])

    rows = [
        stage_row("Path management", "Ready", f"paths_local.yaml loaded: {local_paths.data_root}"),
        stage_row("Project readiness", "Ready", "Python/import/path checks available via check_project_readiness.py"),
        stage_row("Session manifest", "Ready", f"{session_summary.get('total_sessions')} template sessions"),
        stage_row("Session files", "Missing data expected", f"{count_missing(session_findings)} missing template data paths"),
        stage_row("Dataset manifest", "Ready", f"{dataset_summary.get('dataset', {}).get('name')} template only"),
        stage_row("Dataset files", "Missing data expected", f"{count_missing(dataset_findings)} missing dataset paths"),
        stage_row("Model registry", "Ready", f"{model_summary.get('total_models')} planned model(s)"),
        stage_row("Model weights", "Missing data expected", f"model {model_entry.get('status')} does not require best.pt yet"),
        stage_row("Fixed KF", "Ready", "Replay smoke command supported"),
        stage_row("Reliability-aware KF", "Ready", "Replay smoke command supported"),
        stage_row("Evaluation", "Ready", "raw/filtered/reliability metrics supported"),
        stage_row("Ablation", "Ready", "raw_pnp/fixed_kf/reliability_kf command generated"),
        stage_row("Mocap GT evaluation", "Placeholder", "--gt-csv is reserved, full GT comparison not implemented"),
        stage_row("Real Hikrobot calibration", "Pending", "requires lab camera/lens/board"),
        stage_row("Real data capture", "Pending", "requires lab hardware and G-drive data folders"),
        stage_row("Training", "Pending", "train command is generated but not executed"),
    ]
    for name, result in smoke_results.items():
        rows.append(stage_row(name, "Passed" if result["success"] else "Failed", f"returncode={result['returncode']}"))

    summary = {
        "run_name": args.run_name,
        "output_dir": str(output_dir),
        "paths": {
            "project_root": str(local_paths.project_root),
            "data_root": str(local_paths.data_root),
            "outputs_root": str(local_paths.outputs_root),
            "models_root": str(local_paths.models_root),
            "results_root": str(local_paths.results_root),
        },
        "session_summary": session_summary,
        "dataset_summary": dataset_summary,
        "model_summary": model_summary,
        "readiness_rows": rows,
        "missing_data": {
            "session_missing_count": count_missing(session_findings),
            "dataset_missing_count": count_missing(dataset_findings),
            "model_findings": model_findings,
        },
        "executed_commands": smoke_results,
        "generated_commands": commands,
    }

    (output_dir / "workflow_readiness_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_summary_csv(output_dir / "workflow_readiness_summary.csv", rows)
    write_generated_commands(output_dir / "generated_commands.md", commands)
    write_report(
        output_dir / "workflow_dryrun_report.md",
        args=args,
        local_paths=local_paths,
        session_summary=session_summary,
        dataset_summary=dataset_summary,
        model_summary=model_summary,
        rows=rows,
        commands=commands,
    )

    print(
        json.dumps(
            {
                "status": "ok",
                "output_dir": str(output_dir),
                "summary_json": str(output_dir / "workflow_readiness_summary.json"),
                "report": str(output_dir / "workflow_dryrun_report.md"),
                "generated_commands": str(output_dir / "generated_commands.md"),
                "executed_smoke_tests": bool(args.execute_smoke_tests),
                "executed_ablation_smoke": bool(args.execute_ablation_smoke),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
