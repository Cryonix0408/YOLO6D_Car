"""Create or append a session manifest entry from a capture session folder."""

from __future__ import annotations

import argparse
import json
import shutil
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
from yolo6d_car.session_manifest import load_session_manifest, validate_session_manifest


def parse_args() -> argparse.Namespace:
    """Parse registration arguments."""
    parser = argparse.ArgumentParser(description="Register a capture folder as a session manifest entry.")
    parser.add_argument("--capture-root", required=True, help="Capture root, e.g. captures/date/session.")
    parser.add_argument("--paths-config", default=None, help="Optional paths YAML, e.g. configs/paths_local.yaml.")
    parser.add_argument("--manifest", default=None, help="Session manifest YAML to append to.")
    parser.add_argument("--session-id", required=True, help="New unique session id.")
    parser.add_argument("--camera-type", required=True, help="Camera type, e.g. d455/hikrobot/webcam.")
    parser.add_argument("--lens", default=None, help="Optional lens label, e.g. 6mm.")
    parser.add_argument("--intrinsics", default=None, help="Camera intrinsics path or TODO placeholder.")
    parser.add_argument("--motion-type", required=True, help="Motion type, e.g. static/lateral/rotation.")
    parser.add_argument("--speed-level", required=True, help="Speed level, e.g. static/slow/medium/fast.")
    parser.add_argument("--split", required=True, help="Dataset split, e.g. train/val/test.")
    parser.add_argument("--object", default="car", help="Object name.")
    parser.add_argument("--occlusion", default="none", help="Occlusion label.")
    parser.add_argument("--lighting", default="normal", help="Lighting label.")
    parser.add_argument("--background", default="lab", help="Background label.")
    parser.add_argument("--mocap-csv", default="TODO", help="Mocap CSV path; may stay TODO initially.")
    parser.add_argument("--camera-rigid", default="TODO", help="Mocap camera rigid body name.")
    parser.add_argument("--object-rigid", default="car_rigid", help="Mocap object rigid body name.")
    parser.add_argument("--dry-run", action="store_true", help="Print YAML block only; do not write manifest.")
    parser.add_argument("--append", action="store_true", help="Append generated entry to --manifest.")
    return parser.parse_args()


def resolve_cli_path(raw_path: str, paths_config: str | None) -> Path:
    """Resolve a CLI path using paths_local.yaml when provided."""
    local_paths = load_local_paths(paths_config) if paths_config else None
    path = resolve_path(raw_path, project_root=ROOT, local_paths=local_paths)
    if path is None:
        raise ValueError(f"Path is required: {raw_path}")
    return path.resolve()


def data_relative_path(path: Path, paths_config: str | None) -> str:
    """Return a manifest-friendly path relative to data_root when possible."""
    if paths_config:
        local_paths = load_local_paths(paths_config)
        try:
            return path.resolve().relative_to(local_paths.data_root).as_posix()
        except ValueError:
            pass
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def load_capture_metadata(capture_root: Path) -> dict[str, Any]:
    """Load capture_metadata.json if present."""
    path = capture_root / "capture_metadata.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def infer_date(session_id: str, capture_root: Path, metadata: dict[str, Any]) -> str:
    """Infer session date from session_id, capture path, or metadata."""
    prefix = session_id[:10]
    if len(prefix) == 10 and prefix[4] == "-" and prefix[7] == "-":
        return prefix
    created_at = str(metadata.get("created_at", ""))
    if len(created_at) >= 10:
        return created_at[:10]
    for part in capture_root.parts:
        if len(part) == 10 and part[4] == "-" and part[7] == "-":
            return part
    return datetime.now().strftime("%Y-%m-%d")


def build_session_entry(args: argparse.Namespace, capture_root: Path) -> dict[str, Any]:
    """Build a manifest-compatible session entry."""
    metadata = load_capture_metadata(capture_root)
    capture_rel = data_relative_path(capture_root, args.paths_config)
    session_id = args.session_id
    intrinsics = args.intrinsics
    if intrinsics is None:
        intrinsics = "configs/local_smoke_replay.yaml" if args.camera_type == "d455" else "TODO"
    return {
        "session_id": session_id,
        "date": infer_date(session_id, capture_root, metadata),
        "object": args.object,
        "camera": {
            "type": args.camera_type,
            "lens": args.lens,
            "intrinsics": intrinsics,
        },
        "mocap": {
            "enabled": False if args.mocap_csv == "TODO" else True,
            "csv_path": args.mocap_csv,
            "camera_rigid": args.camera_rigid,
            "object_rigid": args.object_rigid,
        },
        "capture": {
            "root": capture_rel,
            "images_dir": "images",
            "videos_dir": "videos",
            "metadata": "capture_metadata.json",
        },
        "motion": {
            "type": args.motion_type,
            "speed_level": args.speed_level,
            "occlusion": args.occlusion,
            "lighting": args.lighting,
            "background": args.background,
        },
        "outputs": {
            "auto_labels": f"outputs/auto_labels/{session_id}",
            "dataset_split": args.split,
            "replay_config": f"outputs/replay_configs/{session_id}.yaml",
            "ablation_run_name": session_id,
        },
    }


def yaml_block(entry: dict[str, Any]) -> str:
    """Render a single-entry YAML block."""
    return yaml.safe_dump([entry], sort_keys=False, allow_unicode=True)


def append_to_manifest(manifest_path: Path, entry: dict[str, Any], paths_config: str | None) -> Path:
    """Append entry to manifest with duplicate protection and backup."""
    manifest = load_session_manifest(manifest_path, paths_config=paths_config)
    existing = {str(session.get("session_id")) for session in manifest.get("sessions", [])}
    session_id = str(entry["session_id"])
    if session_id in existing:
        raise ValueError(f"session_id already exists in manifest: {session_id}")

    updated = dict(manifest)
    updated["sessions"] = list(manifest.get("sessions", [])) + [entry]
    validate_session_manifest(updated)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = manifest_path.with_suffix(manifest_path.suffix + f".bak_{timestamp}")
    shutil.copy2(manifest_path, backup_path)
    manifest_path.write_text(yaml.safe_dump(updated, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return backup_path


def main() -> None:
    """Entrypoint."""
    args = parse_args()
    capture_root = resolve_cli_path(args.capture_root, args.paths_config)
    entry = build_session_entry(args, capture_root)

    # Validate by wrapping the new entry in a minimal manifest skeleton.
    validate_session_manifest(
        {
            "dataset": {
                "name": "preview_dataset",
                "description": "Preview manifest for generated entry validation",
                "data_root": "G:/YOLO6D_Car_Data",
                "created_by": "Yiyang",
                "version": "preview",
            },
            "sessions": [entry],
        }
    )

    if args.dry_run or not args.append:
        print(yaml.safe_dump({"sessions": [entry]}, sort_keys=False, allow_unicode=True))
        return None

    if args.manifest is None:
        raise SystemExit("--manifest is required when using --append")
    manifest_path = Path(args.manifest).resolve()
    backup_path = append_to_manifest(manifest_path, entry, args.paths_config)
    print(
        json.dumps(
            {
                "status": "ok",
                "manifest": str(manifest_path),
                "backup": str(backup_path),
                "session_id": entry["session_id"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
