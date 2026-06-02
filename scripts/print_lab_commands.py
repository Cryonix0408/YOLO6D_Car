"""Print lab-day commands without executing real tasks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.path_utils import load_local_paths, resolve_path


PYTHON = r"D:\Envs\yolo6d\python.exe"


def parse_args() -> argparse.Namespace:
    """Parse command printer arguments."""
    parser = argparse.ArgumentParser(description="Print YOLO6D_Car lab execution commands without running them.")
    parser.add_argument("--paths-config", default="configs/paths_local.yaml", help="Local paths YAML.")
    parser.add_argument("--sessions", required=True, help="Real-session manifest/template YAML.")
    parser.add_argument("--session-id", default=None, help="Optional session_id filter.")
    parser.add_argument("--lens", choices=["6mm", "8mm"], default=None, help="Optional lens filter.")
    parser.add_argument("--output", default=None, help="Optional Markdown output path.")
    return parser.parse_args()


def resolve_cli_path(raw_path: str, paths_config: str | None) -> Path:
    """Resolve command-line path with project/data root rules."""
    local_paths = load_local_paths(paths_config) if paths_config else None
    path = resolve_path(raw_path, project_root=ROOT, local_paths=local_paths)
    if path is None:
        raise ValueError(f"Path is required: {raw_path}")
    return path.resolve()


def load_sessions(path: Path) -> list[dict[str, Any]]:
    """Load sessions from a manifest-like YAML."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sessions = raw.get("sessions", raw.get("planned_sessions", []))
    if not isinstance(sessions, list):
        raise ValueError(f"sessions must be a list in {path}")
    return [session for session in sessions if isinstance(session, dict)]


def filter_sessions(sessions: list[dict[str, Any]], session_id: str | None, lens: str | None) -> list[dict[str, Any]]:
    """Filter sessions by id and lens."""
    result = []
    for session in sessions:
        camera = session.get("camera", {}) if isinstance(session.get("camera"), dict) else {}
        if session_id and str(session.get("session_id")) != session_id:
            continue
        if lens and str(camera.get("lens")) != lens:
            continue
        result.append(session)
    return result


def ps(command: list[str]) -> str:
    """Format a list as a multi-line PowerShell command."""
    if len(command) <= 1:
        return " ".join(command)
    lines = [command[0]]
    index = 1
    while index < len(command):
        if command[index].startswith("--") and index + 1 < len(command) and not command[index + 1].startswith("--"):
            lines.append(f"  {command[index]} {command[index + 1]}")
            index += 2
        else:
            lines.append(f"  {command[index]}")
            index += 1
    return " ^\n".join(lines)


def block(title: str, command: list[str]) -> list[str]:
    """Render one command block."""
    return [f"### {title}", "", "```powershell", ps(command), "```", ""]


def session_commands(session: dict[str, Any], paths_config: str, sessions_file: str) -> list[str]:
    """Render command blocks for one session."""
    session_id = str(session["session_id"])
    date = str(session.get("date", "TODO_DATE"))
    camera = session.get("camera", {})
    mocap = session.get("mocap", {})
    capture = session.get("capture", {})
    motion = session.get("motion", {})
    outputs = session.get("outputs", {})
    lens = camera.get("lens")
    camera_type = camera.get("type", "hikrobot")
    capture_root = str(capture.get("root", f"captures/{date}/{session_id}"))
    images_root = str(Path(capture_root) / str(capture.get("images_dir", "images")))
    auto_labels = str(outputs.get("auto_labels", f"outputs/auto_labels/{session_id}"))
    replay_config = str(outputs.get("replay_config", f"outputs/replay_configs/{session_id}.yaml"))
    split = str(outputs.get("dataset_split", "train"))
    motion_type = str(motion.get("type", "TODO"))
    speed = str(motion.get("speed_level", "TODO"))
    csv_path = str(mocap.get("csv_path", f"FZmotion_Data/raw_csv/{session_id}.csv"))
    camera_rigid = str(mocap.get("camera_rigid", "hik_rigid"))
    object_rigid = str(mocap.get("object_rigid", "car_rigid"))

    lines = [
        f"## Session `{session_id}`",
        "",
        f"- camera: `{camera_type}`",
        f"- lens: `{lens}`",
        f"- motion: `{motion_type}`",
        f"- speed: `{speed}`",
        f"- split: `{split}`",
        "",
    ]
    lines += block(
        "Auto capture",
        [PYTHON, "scripts/capture_object_samples.py", "--config", "configs/object_capture_auto.yaml", "--paths-config", paths_config],
    )
    lines += block(
        "Capture quality",
        [PYTHON, "scripts/check_capture_quality.py", "--capture-root", capture_root, "--paths-config", paths_config, "--output-dir", f"results/capture_quality/{session_id}", "--plot"],
    )
    lines += block(
        "Mocap CSV quality",
        [PYTHON, "scripts/check_mocap_csv.py", "--csv-path", csv_path, "--paths-config", paths_config, "--camera-rigid", camera_rigid, "--object-rigid", object_rigid, "--output-dir", f"results/mocap_quality/{session_id}", "--plot"],
    )
    lines += block(
        "Register session",
        [
            PYTHON,
            "scripts/register_capture_session.py",
            "--capture-root",
            capture_root,
            "--paths-config",
            paths_config,
            "--manifest",
            sessions_file,
            "--session-id",
            session_id,
            "--camera-type",
            str(camera_type),
            "--motion-type",
            motion_type,
            "--speed-level",
            speed,
            "--split",
            split,
            "--append",
        ],
    )
    lines += block(
        "Generate mocap labels",
        [
            PYTHON,
            "scripts/generate_mocap_labels.py",
            "--config",
            str(camera.get("intrinsics", "TODO_LABEL_CONFIG.yaml")),
            "--paths-config",
            paths_config,
            "--samples-dir",
            capture_root,
            "--output-dir",
            auto_labels,
            "--csv-path",
            csv_path,
            "--save-overlays",
        ],
    )
    lines += block(
        "Visualize auto labels",
        [PYTHON, "scripts/visualize_auto_labels.py", "--labels-root", auto_labels, "--images-root", images_root, "--paths-config", paths_config, "--output-dir", f"results/label_visualization/{session_id}", "--max-samples", "100"],
    )
    lines += block(
        "Process single session",
        [PYTHON, "scripts/process_single_session.py", "--session-id", session_id, "--manifest", sessions_file, "--paths-config", paths_config, "--output-dir", f"results/session_processing/{session_id}"],
    )
    lines += block(
        "Ablation",
        [PYTHON, "scripts/run_kalman_ablation.py", "--config", replay_config, "--paths-config", paths_config, "--run-name", session_id, "--max-frames", "300", "--plot"],
    )
    return lines


def render(args: argparse.Namespace, sessions: list[dict[str, Any]]) -> str:
    """Render all lab commands as Markdown."""
    lines = [
        "# Lab Commands Generated",
        "",
        "These commands are printed only. This document does not execute calibration, capture, training, or ablation.",
        "",
        "## Global Checks",
        "",
    ]
    lines += block("Readiness check", [PYTHON, "scripts/check_project_readiness.py", "--paths-config", args.paths_config])
    lines += block("6mm calibration validate", [PYTHON, "scripts/calibrate_hik_camera.py", "--config", "configs/calibration_hik_6mm.yaml", "--paths-config", args.paths_config, "--validate-config"])
    lines += block("8mm calibration validate", [PYTHON, "scripts/calibrate_hik_camera.py", "--config", "configs/calibration_hik_8mm.yaml", "--paths-config", args.paths_config, "--validate-config"])
    lines += block("6mm calibration", [PYTHON, "scripts/calibrate_hik_camera.py", "--config", "configs/calibration_hik_6mm.yaml", "--paths-config", args.paths_config, "--mode", "capture_and_calibrate"])
    lines += block("8mm calibration", [PYTHON, "scripts/calibrate_hik_camera.py", "--config", "configs/calibration_hik_8mm.yaml", "--paths-config", args.paths_config, "--mode", "capture_and_calibrate"])
    lines += block("Manage sessions validate", [PYTHON, "scripts/manage_sessions.py", "--manifest", args.sessions, "--paths-config", args.paths_config, "--action", "validate"])
    lines += block("Generate dataset.yaml", [PYTHON, "scripts/manage_datasets.py", "--manifest", "configs/dataset_manifest_template.yaml", "--paths-config", args.paths_config, "--action", "generate-data-yaml"])
    lines += block("Print train command", [PYTHON, "scripts/manage_models.py", "--registry", "configs/model_registry_template.yaml", "--paths-config", args.paths_config, "--action", "print-train-command", "--model-id", "car_pose_12pts_v1_yolov8n_pose"])
    for session in sessions:
        lines.extend(session_commands(session, args.paths_config, args.sessions))
    return "\n".join(lines)


def main() -> int:
    """Print or write lab commands."""
    args = parse_args()
    sessions_path = resolve_cli_path(args.sessions, args.paths_config)
    sessions = filter_sessions(load_sessions(sessions_path), args.session_id, args.lens)
    markdown = render(args, sessions)
    if args.output:
        output = resolve_cli_path(args.output, args.paths_config)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(markdown + "\n", encoding="utf-8")
        print(f"Wrote lab commands: {output}")
        print(f"Sessions included: {len(sessions)}")
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
