"""Generate a Markdown checklist for one YOLO6D_Car experiment day."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.path_utils import load_local_paths, resolve_path


def parse_args() -> argparse.Namespace:
    """Parse checklist generation arguments."""
    parser = argparse.ArgumentParser(description="Generate an experiment-day checklist from planned sessions.")
    parser.add_argument("--date", required=True, help="Experiment date, e.g. 2026-05-30.")
    parser.add_argument("--planned-sessions", required=True, help="Planned sessions YAML.")
    parser.add_argument("--paths-config", default=None, help="Optional paths YAML, e.g. configs/paths_local.yaml.")
    parser.add_argument("--output", required=True, help="Output Markdown path.")
    return parser.parse_args()


def resolve_cli_path(raw_path: str, paths_config: str | None) -> Path:
    """Resolve a CLI path using project D-drive / data G-drive rules."""
    local_paths = load_local_paths(paths_config) if paths_config else None
    path = resolve_path(raw_path, project_root=ROOT, local_paths=local_paths)
    if path is None:
        raise ValueError(f"Path is required: {raw_path}")
    return path.resolve()


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML mapping."""
    if not path.exists():
        raise FileNotFoundError(f"Planned sessions file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Planned sessions YAML root must be a mapping: {path}")
    return data


def planned_sessions(data: dict[str, Any], date_text: str) -> list[dict[str, Any]]:
    """Return planned sessions for the requested date."""
    defaults = data.get("defaults") if isinstance(data.get("defaults"), dict) else {}
    raw_sessions = data.get("planned_sessions", data.get("sessions", []))
    if not isinstance(raw_sessions, list):
        raise ValueError("planned_sessions or sessions must be a list.")

    sessions: list[dict[str, Any]] = []
    for raw in raw_sessions:
        if not isinstance(raw, dict):
            continue
        session = {**defaults, **raw}
        session_date = str(session.get("date") or session.get("session_id", "")[:10])
        if session_date == date_text:
            sessions.append(session)
    return sessions


def checkbox(text: str) -> str:
    """Return one Markdown checkbox line."""
    return f"- [ ] {text}"


def session_table(sessions: list[dict[str, Any]]) -> list[str]:
    """Build the planned session table."""
    lines = [
        "| Done | session_id | motion | speed | camera | lens | camera rigid | object rigid | lighting | background | notes |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for session in sessions:
        lines.append(
            "| [ ] "
            f"| `{session.get('session_id', '')}` "
            f"| {session.get('motion_type', session.get('motion', ''))} "
            f"| {session.get('speed_level', '')} "
            f"| {session.get('camera_type', '')} "
            f"| {session.get('lens', '')} "
            f"| `{session.get('camera_rigid', '')}` "
            f"| `{session.get('object_rigid', '')}` "
            f"| {session.get('lighting', '')} "
            f"| {session.get('background', '')} "
            f"| {session.get('notes', '')} |"
        )
    return lines


def render_checklist(date_text: str, plan: dict[str, Any], paths_config: str | None, sessions: list[dict[str, Any]]) -> str:
    """Render the full experiment-day checklist Markdown."""
    local_paths = load_local_paths(paths_config) if paths_config else None
    experiment = plan.get("experiment_day") if isinstance(plan.get("experiment_day"), dict) else {}
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = [
        f"# Experiment Day Checklist - {date_text}",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Operator: `{experiment.get('operator', '')}`",
        f"- Location: `{experiment.get('location', '')}`",
        f"- Objective: {experiment.get('objective', '')}",
        "",
        "## Path Summary",
        "",
        f"- Project root: `{ROOT}`",
    ]
    if local_paths:
        lines.extend(
            [
                f"- Data root: `{local_paths.data_root}`",
                f"- Captures root: `{local_paths.captures_root}`",
                f"- FZmotion root: `{local_paths.fzmotion_root}`",
                f"- Outputs root: `{local_paths.outputs_root}`",
                f"- Results root: `{local_paths.results_root}`",
            ]
        )

    lines.extend(
        [
            "",
            "## 1. Hardware Check",
            "",
            checkbox("RealSense D455 connected and recognized"),
            checkbox("Hikrobot MV-CS016-10UC connected and recognized"),
            checkbox("6mm lens present, clean, and tightened"),
            checkbox("8mm lens present, clean, and tightened"),
            checkbox("Chessboard / ChArUco calibration board present"),
            checkbox("Small car object present and marker mounts intact"),
            checkbox("Mocap markers attached and visible"),
            checkbox("Lighting / fill light available and stable"),
            checkbox("Power, USB cables, hubs, and camera mounts checked"),
            checkbox("G drive / capture storage space checked"),
            "",
            "## 2. Software Check",
            "",
            "```powershell",
            "D:\\Envs\\yolo6d\\python.exe scripts\\check_project_readiness.py --paths-config configs\\paths_local.yaml",
            "```",
            checkbox("Project readiness check passed"),
            "",
            "```powershell",
            "D:\\Envs\\yolo6d\\python.exe scripts\\capture_object_samples.py --config configs\\object_capture_auto.yaml --paths-config configs\\paths_local.yaml --validate-config",
            "```",
            checkbox("Auto capture validate-config passed"),
            "",
            "```powershell",
            "D:\\Envs\\yolo6d\\python.exe scripts\\capture_object_samples.py --config configs\\object_capture_auto.yaml --paths-config configs\\paths_local.yaml --dry-run --max-frames 20",
            "```",
            checkbox("Auto capture dry-run passed"),
            checkbox("FzMotion CSV save path set to `G:\\YOLO6D_Car_Data\\FZmotion_Data\\raw_csv`"),
            checkbox("Sync script command reviewed"),
            "",
            "```powershell",
            "D:\\Envs\\yolo6d\\python.exe scripts\\sync_capture_to_host.py --help",
            "```",
            "",
            "## 3. Calibration Tasks",
            "",
            "### 6mm Hikrobot Lens",
            "",
            "```powershell",
            "D:\\Envs\\yolo6d\\python.exe scripts\\calibrate_hik_camera.py --config configs\\calibration_hik_6mm.yaml --paths-config configs\\paths_local.yaml --validate-config",
            "```",
            checkbox("6mm calibration validate-config passed"),
            checkbox("6mm auto calibration completed"),
            checkbox("6mm intrinsics saved under `G:\\YOLO6D_Car_Data\\outputs\\calibration\\hik_6mm`"),
            "",
            "### 8mm Hikrobot Lens",
            "",
            "```powershell",
            "D:\\Envs\\yolo6d\\python.exe scripts\\calibrate_hik_camera.py --config configs\\calibration_hik_8mm.yaml --paths-config configs\\paths_local.yaml --validate-config",
            "```",
            checkbox("8mm calibration validate-config passed"),
            checkbox("8mm auto calibration completed"),
            checkbox("8mm intrinsics saved under `G:\\YOLO6D_Car_Data\\outputs\\calibration\\hik_8mm`"),
            "",
            "## 4. Planned Capture Sessions",
            "",
        ]
    )
    if sessions:
        lines.extend(session_table(sessions))
    else:
        lines.append("> No planned sessions found for this date.")

    lines.extend(
        [
            "",
            "## 5. Per-Session Notes Template",
            "",
        ]
    )
    for session in sessions:
        session_id = str(session.get("session_id", ""))
        lines.extend(
            [
                f"### {session_id}",
                "",
                checkbox("Capture session completed"),
                checkbox("Mocap CSV saved"),
                checkbox("capture_metadata.json checked"),
                checkbox("capture_index.csv checked"),
                checkbox("Lighting/background notes recorded"),
                checkbox("Any failure or unusual motion written below"),
                "",
                "- Notes:",
                "",
            ]
        )

    lines.extend(
        [
            "## 6. End-of-Day Checks",
            "",
            checkbox("Run capture quality check for each session"),
            checkbox("Run mocap CSV quality check for each session"),
            checkbox("Register capture sessions into session manifest"),
            checkbox("Sync laptop captures to workstation G drive"),
            checkbox("Backup captures and FzMotion CSV"),
            checkbox("Confirm no large files were committed into Git"),
            "",
            "Example commands:",
            "",
            "```powershell",
            "D:\\Envs\\yolo6d\\python.exe scripts\\check_capture_quality.py --capture-root captures\\<date>\\<session_id> --paths-config configs\\paths_local.yaml --output-dir results\\capture_quality\\<session_id> --plot",
            "D:\\Envs\\yolo6d\\python.exe scripts\\check_mocap_csv.py --csv-path FZmotion_Data\\raw_csv\\<session_id>.csv --paths-config configs\\paths_local.yaml --camera-rigid <camera_rigid> --object-rigid car_rigid --output-dir results\\mocap_quality\\<session_id> --plot",
            "D:\\Envs\\yolo6d\\python.exe scripts\\register_capture_session.py --capture-root captures\\<date>\\<session_id> --paths-config configs\\paths_local.yaml --manifest configs\\session_manifest_template.yaml --session-id <session_id> --camera-type <camera_type> --motion-type <motion_type> --speed-level <speed_level> --split train --append",
            "```",
            "",
            "## 7. Session Coverage Reminder",
            "",
            checkbox("Static baseline captured"),
            checkbox("Slow lateral captured"),
            checkbox("Fast lateral captured"),
            checkbox("Approach captured"),
            checkbox("Receding captured"),
            checkbox("Rotation captured"),
            checkbox("Occlusion captured"),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    """Generate the checklist file."""
    args = parse_args()
    planned_path = resolve_cli_path(args.planned_sessions, args.paths_config)
    output_path = resolve_cli_path(args.output, args.paths_config)
    plan = load_yaml(planned_path)
    sessions = planned_sessions(plan, args.date)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_checklist(args.date, plan, args.paths_config, sessions), encoding="utf-8")
    print(f"Wrote experiment checklist: {output_path}")
    print(f"Planned sessions for {args.date}: {len(sessions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
