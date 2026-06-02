"""Run or dry-run the processing steps for one capture session."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.path_utils import load_local_paths, resolve_path
from yolo6d_car.session_manifest import load_session_manifest, resolve_session_paths, write_replay_config


@dataclass
class StepResult:
    """Result for one processing step."""

    name: str
    command: list[str]
    status: str
    returncode: int | None
    stdout: str
    stderr: str
    reason: str | None = None


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Process one YOLO6D_Car session through quality, labeling, and replay-config steps.")
    parser.add_argument("--session-id", required=True, help="Session id to process.")
    parser.add_argument("--manifest", required=True, help="Session manifest YAML.")
    parser.add_argument("--paths-config", default=None, help="Optional paths YAML, e.g. configs/paths_local.yaml.")
    parser.add_argument("--output-dir", required=True, help="Directory for process reports.")
    parser.add_argument("--dry-run", action="store_true", help="Only generate commands and reports; do not execute processing steps.")
    parser.add_argument("--python", default=sys.executable, help="Python executable used for child scripts.")
    parser.add_argument("--max-label-visualization-samples", type=int, default=100, help="Maximum labels to visualize.")
    parser.add_argument("--plot", action="store_true", help="Pass --plot to quality-check scripts.")
    return parser.parse_args()


def resolve_cli_path(raw_path: str, paths_config: str | None) -> Path:
    """Resolve a CLI path with optional D/G-drive path rules."""
    local_paths = load_local_paths(paths_config) if paths_config else None
    path = resolve_path(raw_path, project_root=ROOT, local_paths=local_paths)
    if path is None:
        raise ValueError(f"Path is required: {raw_path}")
    return path.resolve()


def find_session(manifest: dict[str, Any], session_id: str) -> dict[str, Any]:
    """Return one session from a loaded manifest."""
    for session in manifest.get("sessions", []):
        if str(session.get("session_id")) == session_id:
            return session
    raise ValueError(f"Session id not found in manifest: {session_id}")


def command_to_text(command: list[str]) -> str:
    """Return a readable PowerShell-friendly command line."""
    parts = []
    for part in command:
        text = str(part)
        if any(char.isspace() for char in text):
            parts.append(f'"{text}"')
        else:
            parts.append(text)
    return " ".join(parts)


def run_step(name: str, command: list[str], *, dry_run: bool) -> StepResult:
    """Run one subprocess step or record it as skipped during dry-run."""
    if dry_run:
        return StepResult(name=name, command=command, status="dry_run", returncode=None, stdout="", stderr="", reason="dry-run; command not executed")
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    status = "success" if completed.returncode == 0 else "failed"
    return StepResult(
        name=name,
        command=command,
        status=status,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def record_skipped(name: str, command: list[str], reason: str) -> StepResult:
    """Record a skipped step with a clear reason."""
    return StepResult(name=name, command=command, status="skipped", returncode=None, stdout="", stderr="", reason=reason)


def build_commands(args: argparse.Namespace, session: dict[str, Any], output_dir: Path) -> dict[str, list[str]]:
    """Build commands for all external processing steps."""
    capture = session.get("capture", {})
    mocap = session.get("mocap", {})
    outputs = session.get("outputs", {})
    camera = session.get("camera", {})

    capture_root = str(capture.get("root", ""))
    images_dir = str(capture.get("images_dir", "images"))
    images_root = str(Path(capture_root) / images_dir)
    auto_labels = str(outputs.get("auto_labels", f"outputs/auto_labels/{args.session_id}"))
    mocap_csv = mocap.get("csv_path")
    camera_rigid = str(mocap.get("camera_rigid", ""))
    object_rigid = str(mocap.get("object_rigid", ""))
    label_config = str(camera.get("intrinsics") or "")

    def add_paths_config(command: list[str]) -> list[str]:
        if args.paths_config:
            command.extend(["--paths-config", args.paths_config])
        return command

    check_capture = add_paths_config([
        args.python,
        "scripts/check_capture_quality.py",
        "--capture-root",
        capture_root,
        "--output-dir",
        str(output_dir / "capture_quality"),
    ])
    if args.plot:
        check_capture.append("--plot")

    check_mocap = add_paths_config([
        args.python,
        "scripts/check_mocap_csv.py",
        "--csv-path",
        "" if mocap_csv is None else str(mocap_csv),
        "--camera-rigid",
        camera_rigid,
        "--object-rigid",
        object_rigid,
        "--output-dir",
        str(output_dir / "mocap_quality"),
    ])
    if args.plot:
        check_mocap.append("--plot")

    generate_labels = add_paths_config([
        args.python,
        "scripts/generate_mocap_labels.py",
        "--config",
        label_config,
        "--samples-dir",
        capture_root,
        "--output-dir",
        auto_labels,
        "--csv-path",
        "" if mocap_csv is None else str(mocap_csv),
        "--save-overlays",
    ])

    visualize_labels = add_paths_config([
        args.python,
        "scripts/visualize_auto_labels.py",
        "--labels-root",
        auto_labels,
        "--images-root",
        images_root,
        "--output-dir",
        str(output_dir / "label_visualization"),
        "--max-samples",
        str(args.max_label_visualization_samples),
    ])

    validate_manifest = [
        args.python,
        "scripts/manage_sessions.py",
        "--manifest",
        args.manifest,
        "--action",
        "validate",
    ]
    add_paths_config(validate_manifest)

    return {
        "validate session manifest": validate_manifest,
        "check capture quality": check_capture,
        "check mocap csv": check_mocap,
        "generate mocap labels": generate_labels,
        "visualize auto labels": visualize_labels,
        "generate replay config": ["internal", "write_replay_config", args.session_id],
    }


def should_skip_mocap(session: dict[str, Any]) -> str | None:
    """Return a skip reason for mocap-dependent steps, if any."""
    mocap = session.get("mocap", {})
    if not bool(mocap.get("enabled")):
        return "session.mocap.enabled is false"
    if not mocap.get("csv_path"):
        return "session.mocap.csv_path is empty"
    if not mocap.get("camera_rigid") or not mocap.get("object_rigid"):
        return "session.mocap.camera_rigid or object_rigid is empty"
    return None


def run_internal_replay_config(args: argparse.Namespace, session: dict[str, Any], command: list[str]) -> StepResult:
    """Generate a replay config for a single session."""
    if args.dry_run:
        return StepResult(
            name="generate replay config",
            command=command,
            status="dry_run",
            returncode=None,
            stdout="",
            stderr="",
            reason="dry-run; replay config not written",
        )
    try:
        path = write_replay_config(session, args.paths_config)
    except Exception as exc:
        return StepResult(
            name="generate replay config",
            command=command,
            status="failed",
            returncode=1,
            stdout="",
            stderr=str(exc),
        )
    return StepResult(
        name="generate replay config",
        command=command,
        status="success",
        returncode=0,
        stdout=f"Replay config written: {path}",
        stderr="",
    )


def write_generated_commands(path: Path, commands: dict[str, list[str]]) -> None:
    """Write a markdown file with all generated commands."""
    lines = ["# Generated Commands", ""]
    for name, command in commands.items():
        lines.extend([f"## {name}", "", "```powershell", command_to_text(command), "```", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_summary(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON summary."""
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_report(path: Path, summary: dict[str, Any]) -> None:
    """Write a human-readable processing report."""
    session = summary["session"]
    lines = [
        "# Single Session Processing Report",
        "",
        f"- Session ID: `{session.get('session_id')}`",
        f"- Dry run: `{summary['dry_run']}`",
        f"- Overall status: **{summary['overall_status']}**",
        f"- Created at: `{summary['created_at']}`",
        "",
        "## Resolved Paths",
        "",
    ]
    for key, value in summary["resolved_paths"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Steps", ""])
    lines.append("| Step | Status | Return Code | Notes |")
    lines.append("|---|---:|---:|---|")
    for step in summary["steps"]:
        note = step.get("reason") or ""
        if step.get("status") == "failed":
            note = step.get("stderr", "").strip().splitlines()[0] if step.get("stderr") else "failed"
        lines.append(f"| {step['name']} | {step['status']} | {step.get('returncode')} | {note} |")
    lines.extend(["", "## Failure Handling", ""])
    if summary["overall_status"] == "success":
        lines.append("All required executed steps completed successfully.")
    elif summary["overall_status"] == "dry_run":
        lines.append("No processing step was executed. Review `generated_commands.md`, then rerun without `--dry-run` when data is ready.")
    else:
        lines.append(summary.get("failure_reason") or "A processing step failed. Inspect stdout/stderr in `process_summary.json`.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    """Run the single-session processing orchestrator."""
    args = parse_args()
    output_dir = resolve_cli_path(args.output_dir, args.paths_config)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_session_manifest(args.manifest, args.paths_config)
    session = find_session(manifest, args.session_id)
    resolved = {key: None if value is None else str(value) for key, value in resolve_session_paths(session, args.paths_config).items()}
    commands = build_commands(args, session, output_dir)
    write_generated_commands(output_dir / "generated_commands.md", commands)

    steps: list[StepResult] = []
    failure_reason: str | None = None

    ordered = [
        "validate session manifest",
        "check capture quality",
        "check mocap csv",
        "generate mocap labels",
        "visualize auto labels",
        "generate replay config",
    ]
    mocap_skip_reason = should_skip_mocap(session)

    for name in ordered:
        command = commands[name]
        if name in {"check mocap csv", "generate mocap labels"} and mocap_skip_reason:
            result = record_skipped(name, command, mocap_skip_reason)
        elif name == "generate replay config":
            result = run_internal_replay_config(args, session, command)
        else:
            result = run_step(name, command, dry_run=args.dry_run)
        steps.append(result)
        if result.status == "failed":
            failure_reason = f"Step failed: {name}"
            break

    if failure_reason:
        overall_status = "failed"
    elif args.dry_run:
        overall_status = "dry_run"
    else:
        overall_status = "success"

    summary = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "session_id": args.session_id,
        "manifest": str(Path(args.manifest).resolve()),
        "paths_config": None if args.paths_config is None else str(Path(args.paths_config).resolve()),
        "output_dir": str(output_dir),
        "dry_run": bool(args.dry_run),
        "overall_status": overall_status,
        "failure_reason": failure_reason,
        "session": session,
        "resolved_paths": resolved,
        "steps": [asdict(step) for step in steps],
    }
    write_summary(output_dir / "process_summary.json", summary)
    write_report(output_dir / "process_report.md", summary)
    print(json.dumps({"status": overall_status, "report": str(output_dir / "process_report.md")}, ensure_ascii=False, indent=2))
    return 0 if overall_status in {"success", "dry_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
