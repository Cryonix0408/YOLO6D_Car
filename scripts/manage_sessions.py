"""本文件作用：
    命令行管理 session manifest：validate、summary、export、生成 replay config、dry-run ablation。

在 YOLO6D_Car pipeline 中的位置：
    实验数据管理层。session manifest 记录每一次采集 session 的相机、mocap、capture 和输出路径。

注意事项：
    validate 只检查结构，不要求真实数据存在；check-files 才检查 captures/FZmotion/outputs。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.path_utils import load_local_paths, resolve_path
from yolo6d_car.session_manifest import (
    check_session_files,
    export_session_table,
    flatten_session,
    list_sessions,
    load_session_manifest,
    summarize_sessions,
    validate_session_manifest,
    write_replay_config,
)


def parse_args() -> argparse.Namespace:
    """Parse session management arguments."""
    parser = argparse.ArgumentParser(description="Validate and operate on YOLO6D_Car session manifests.")
    parser.add_argument("--manifest", required=True, help="Session manifest YAML.")
    parser.add_argument("--paths-config", default=None, help="Optional paths YAML, e.g. configs/paths_local.yaml.")
    parser.add_argument(
        "--action",
        required=True,
        choices=["validate", "summary", "export-table", "check-files", "generate-replay-configs", "run-ablation"],
        help="Action to perform.",
    )
    parser.add_argument("--output", default=None, help="Output CSV path for export-table.")
    parser.add_argument("--speed-level", default=None, help="Filter by motion.speed_level.")
    parser.add_argument("--motion-type", default=None, help="Filter by motion.type.")
    parser.add_argument("--split", default=None, help="Filter by outputs.dataset_split.")
    parser.add_argument("--camera-type", default=None, help="Filter by camera.type.")
    parser.add_argument("--lens", default=None, help="Filter by camera.lens.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them.")
    parser.add_argument("--max-frames", type=int, default=3, help="Max replay frames for run-ablation.")
    parser.add_argument("--plot", action="store_true", help="Pass --plot to run_kalman_ablation.py.")
    parser.add_argument("--python", default=sys.executable, help="Python executable for child ablation runs.")
    return parser.parse_args()


def resolve_cli_path(raw_path: str, paths_config: str | None) -> Path:
    """Resolve CLI paths with optional paths_local.yaml."""
    local_paths = load_local_paths(paths_config) if paths_config else None
    path = resolve_path(raw_path, project_root=ROOT, local_paths=local_paths)
    if path is None:
        raise ValueError(f"Path is required: {raw_path}")
    return path.resolve()


def filters_from_args(args: argparse.Namespace) -> dict[str, str | None]:
    """Collect session filters from CLI args."""
    return {
        "speed_level": args.speed_level,
        "motion_type": args.motion_type,
        "split": args.split,
        "camera_type": args.camera_type,
        "lens": args.lens,
    }


def action_validate(manifest: dict[str, Any]) -> None:
    """Validate manifest and print status."""
    validate_session_manifest(manifest)
    print(json.dumps({"status": "ok", "sessions": len(manifest.get("sessions", []))}, ensure_ascii=False, indent=2))


def action_summary(manifest: dict[str, Any]) -> None:
    """Print manifest summary."""
    print(json.dumps(summarize_sessions(manifest), ensure_ascii=False, indent=2))


def action_export_table(manifest: dict[str, Any], output: str | None, paths_config: str | None) -> None:
    """Export session table CSV."""
    if output is None:
        raise SystemExit("--output is required for --action export-table")
    output_path = resolve_cli_path(output, paths_config)
    export_session_table(manifest, output_path)
    print(json.dumps({"status": "ok", "output": str(output_path)}, ensure_ascii=False, indent=2))


def action_check_files(manifest: dict[str, Any], paths_config: str | None) -> None:
    """Check expected session files and directories."""
    payload = []
    for session in manifest.get("sessions", []):
        payload.append(
            {
                "session_id": session.get("session_id"),
                "findings": check_session_files(session, paths_config),
            }
        )
    missing = sum(1 for item in payload for finding in item["findings"] if finding["status"] != "ok")
    print(json.dumps({"status": "ok", "missing_or_unresolved": missing, "sessions": payload}, ensure_ascii=False, indent=2))


def action_generate_replay_configs(manifest: dict[str, Any], paths_config: str | None) -> None:
    """Generate replay configs for every manifest session."""
    generated = []
    warnings = []
    for session in manifest.get("sessions", []):
        path = write_replay_config(session, paths_config)
        generated.append({"session_id": session.get("session_id"), "replay_config": str(path)})
        warnings.append(
            {
                "session_id": session.get("session_id"),
                "warning": "Set yolo6d.replay_json_path after auto-label/replay predictions are generated.",
            }
        )
    print(json.dumps({"status": "ok", "generated": generated, "warnings": warnings}, ensure_ascii=False, indent=2))


def build_ablation_command(args: argparse.Namespace, session: dict[str, Any]) -> list[str]:
    """Build one run_kalman_ablation.py command for a session."""
    replay_config = str(session["outputs"]["replay_config"])
    run_name = str(session["outputs"].get("ablation_run_name") or session["session_id"])
    command = [
        args.python,
        "scripts/run_kalman_ablation.py",
        "--config",
        replay_config,
        "--run-name",
        run_name,
        "--max-frames",
        str(args.max_frames),
    ]
    if args.paths_config:
        command.extend(["--paths-config", args.paths_config])
    if args.plot:
        command.append("--plot")
    return command


def action_run_ablation(manifest: dict[str, Any], args: argparse.Namespace) -> None:
    """Run or dry-run ablation for filtered sessions."""
    sessions = list_sessions(manifest, filters_from_args(args))
    results = []
    for session in sessions:
        command = build_ablation_command(args, session)
        if args.dry_run:
            results.append({"session_id": session.get("session_id"), "dry_run": True, "command": command})
            continue
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
        results.append(
            {
                "session_id": session.get("session_id"),
                "dry_run": False,
                "returncode": completed.returncode,
                "command": command,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )
    print(json.dumps({"status": "ok", "matched_sessions": len(sessions), "results": results}, ensure_ascii=False, indent=2))


def main() -> None:
    """Entrypoint."""
    args = parse_args()
    manifest = load_session_manifest(args.manifest, paths_config=args.paths_config)

    if args.action == "validate":
        action_validate(manifest)
    elif args.action == "summary":
        action_summary(manifest)
    elif args.action == "export-table":
        action_export_table(manifest, args.output, args.paths_config)
    elif args.action == "check-files":
        action_check_files(manifest, args.paths_config)
    elif args.action == "generate-replay-configs":
        action_generate_replay_configs(manifest, args.paths_config)
    elif args.action == "run-ablation":
        action_run_ablation(manifest, args)
    else:
        raise SystemExit(f"Unsupported action: {args.action}")


if __name__ == "__main__":
    main()
