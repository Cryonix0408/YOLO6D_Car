"""本文件作用：
    管理一次次采集 session 的结构化清单。

在 YOLO6D_Car pipeline 中的位置：
    session 是真实实验的最小单位：一次采集、一份 mocap CSV、一组输出标签/回放配置。
    后续 dataset 构建、replay、ablation 都从 session manifest 找输入。

主要输入：
    configs/session_manifest_template.yaml 或真实 session manifest。

主要输出：
    校验结果、路径解析结果、session 表格、replay config skeleton。

注意事项：
    session manifest 管“数据从哪里来”；dataset manifest 管“哪些 session 组成训练集”；
    model registry 管“哪个模型由哪个 dataset 训练出来”。
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from .path_utils import LocalPaths, load_local_paths, resolve_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class SessionManifestError(ValueError):
    """Raised when a session manifest is structurally invalid."""


def load_session_manifest(path: str | Path, paths_config: str | Path | None = None) -> dict[str, Any]:
    """Load and validate a YAML session manifest.

    ``paths_config`` is accepted for API symmetry and early validation, but the
    manifest itself remains portable because paths are not rewritten in-place.
    """
    manifest_path = Path(path).resolve()
    if not manifest_path.exists():
        raise FileNotFoundError(f"Session manifest not found: {manifest_path}")
    if paths_config is not None:
        load_local_paths(paths_config)
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle) or {}
    validate_session_manifest(manifest)
    return manifest


def validate_session_manifest(manifest: dict[str, Any]) -> None:
    """校验 manifest 结构，但不要求真实文件存在。

    这样设计是为了“先搭工程骨架，再采真实数据”：即使 captures/FZmotion CSV 尚未生成，
    也可以提前规划 session_id、路径、split 和输出位置。
    """
    if not isinstance(manifest, dict):
        raise SessionManifestError("Manifest root must be a mapping.")
    dataset = manifest.get("dataset")
    if not isinstance(dataset, dict):
        raise SessionManifestError("Manifest must contain a 'dataset' mapping.")
    for key in ("name", "description", "data_root", "created_by", "version"):
        if not dataset.get(key):
            raise SessionManifestError(f"dataset.{key} is required.")

    sessions = manifest.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise SessionManifestError("Manifest must contain a non-empty 'sessions' list.")

    seen: set[str] = set()
    for index, session in enumerate(sessions):
        label = f"sessions[{index}]"
        if not isinstance(session, dict):
            raise SessionManifestError(f"{label} must be a mapping.")
        for key in ("session_id", "date", "object", "camera", "mocap", "capture", "motion", "outputs"):
            if key not in session:
                raise SessionManifestError(f"{label}.{key} is required.")
        session_id = str(session.get("session_id", "")).strip()
        if not session_id:
            raise SessionManifestError(f"{label}.session_id is required.")
        if session_id in seen:
            raise SessionManifestError(f"Duplicate session_id: {session_id}")
        seen.add(session_id)

        _require_mapping(session, "camera", ("type", "intrinsics"), label)
        _require_mapping(session, "mocap", ("enabled", "csv_path", "camera_rigid", "object_rigid"), label)
        _require_mapping(session, "capture", ("root", "images_dir", "videos_dir", "metadata"), label)
        _require_mapping(session, "motion", ("type", "speed_level", "occlusion", "lighting", "background"), label)
        _require_mapping(session, "outputs", ("auto_labels", "dataset_split", "replay_config", "ablation_run_name"), label)


def resolve_session_paths(session: dict[str, Any], paths_config: str | Path | None = None) -> dict[str, Path | None]:
    """Resolve important session paths to ``Path`` objects."""
    local_paths = load_local_paths(paths_config) if paths_config is not None else None
    capture = session.get("capture", {})
    outputs = session.get("outputs", {})
    camera = session.get("camera", {})
    mocap = session.get("mocap", {})
    capture_root = _resolve(str(capture.get("root", "")), local_paths)
    return {
        "camera_intrinsics": _resolve(camera.get("intrinsics"), local_paths),
        "mocap_csv": _resolve(mocap.get("csv_path"), local_paths),
        "capture_root": capture_root,
        "images_dir": None if capture_root is None else capture_root / str(capture.get("images_dir", "")),
        "videos_dir": None if capture_root is None else capture_root / str(capture.get("videos_dir", "")),
        "metadata": None if capture_root is None else capture_root / str(capture.get("metadata", "")),
        "auto_labels": _resolve(outputs.get("auto_labels"), local_paths),
        "replay_config": _resolve(outputs.get("replay_config"), local_paths),
    }


def list_sessions(manifest: dict[str, Any], filters: dict[str, str | None] | None = None) -> list[dict[str, Any]]:
    """Return sessions matching optional speed/motion/split/camera/lens filters."""
    filters = {key: value for key, value in (filters or {}).items() if value not in {None, ""}}
    sessions = manifest.get("sessions", [])
    result: list[dict[str, Any]] = []
    for session in sessions:
        if _matches_filters(session, filters):
            result.append(session)
    return result


def summarize_sessions(manifest: dict[str, Any]) -> dict[str, Any]:
    """Summarize session counts for terminal and reports."""
    sessions = manifest.get("sessions", [])
    return {
        "dataset": manifest.get("dataset", {}),
        "total_sessions": len(sessions),
        "by_split": dict(Counter(_nested(session, "outputs", "dataset_split") for session in sessions)),
        "by_speed_level": dict(Counter(_nested(session, "motion", "speed_level") for session in sessions)),
        "by_motion_type": dict(Counter(_nested(session, "motion", "type") for session in sessions)),
        "by_camera_type": dict(Counter(_nested(session, "camera", "type") for session in sessions)),
        "by_lens": dict(Counter(str(_nested(session, "camera", "lens")) for session in sessions)),
    }


def export_session_table(manifest: dict[str, Any], output_csv: str | Path) -> None:
    """Export a flat session summary CSV."""
    output = Path(output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "session_id",
        "date",
        "object",
        "camera_type",
        "lens",
        "intrinsics",
        "mocap_enabled",
        "mocap_csv_path",
        "camera_rigid",
        "object_rigid",
        "capture_root",
        "motion_type",
        "speed_level",
        "occlusion",
        "lighting",
        "background",
        "dataset_split",
        "auto_labels",
        "replay_config",
        "ablation_run_name",
    ]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for session in manifest.get("sessions", []):
            writer.writerow(flatten_session(session))


def flatten_session(session: dict[str, Any]) -> dict[str, Any]:
    """Flatten a session mapping for CSV/JSON tables."""
    return {
        "session_id": session.get("session_id", ""),
        "date": session.get("date", ""),
        "object": session.get("object", ""),
        "camera_type": _nested(session, "camera", "type"),
        "lens": _nested(session, "camera", "lens"),
        "intrinsics": _nested(session, "camera", "intrinsics"),
        "mocap_enabled": _nested(session, "mocap", "enabled"),
        "mocap_csv_path": _nested(session, "mocap", "csv_path"),
        "camera_rigid": _nested(session, "mocap", "camera_rigid"),
        "object_rigid": _nested(session, "mocap", "object_rigid"),
        "capture_root": _nested(session, "capture", "root"),
        "motion_type": _nested(session, "motion", "type"),
        "speed_level": _nested(session, "motion", "speed_level"),
        "occlusion": _nested(session, "motion", "occlusion"),
        "lighting": _nested(session, "motion", "lighting"),
        "background": _nested(session, "motion", "background"),
        "dataset_split": _nested(session, "outputs", "dataset_split"),
        "auto_labels": _nested(session, "outputs", "auto_labels"),
        "replay_config": _nested(session, "outputs", "replay_config"),
        "ablation_run_name": _nested(session, "outputs", "ablation_run_name"),
    }


def check_session_files(session: dict[str, Any], paths_config: str | Path | None = None) -> list[dict[str, str]]:
    """Check expected files/directories for one session and return findings."""
    resolved = resolve_session_paths(session, paths_config)
    expected_kinds = {
        "camera_intrinsics": "file",
        "mocap_csv": "file",
        "capture_root": "dir",
        "images_dir": "dir",
        "videos_dir": "dir",
        "metadata": "file",
        "auto_labels": "dir",
        "replay_config": "file",
    }
    findings: list[dict[str, str]] = []
    for label, path in resolved.items():
        if path is None:
            findings.append({"label": label, "path": "", "status": "missing_path", "expected": expected_kinds[label]})
            continue
        expected = expected_kinds[label]
        exists = path.is_file() if expected == "file" else path.is_dir()
        findings.append(
            {
                "label": label,
                "path": str(path),
                "status": "ok" if exists else "missing",
                "expected": expected,
            }
        )
    return findings


def build_replay_config(session: dict[str, Any]) -> dict[str, Any]:
    """Build a pipeline-compatible replay config skeleton for one session."""
    camera_type = str(_nested(session, "camera", "type") or "d455")
    fps = 30 if camera_type == "hikrobot" else 15
    width = 1440 if camera_type == "hikrobot" else 1280
    height = 1080 if camera_type == "hikrobot" else 720
    session_id = str(session.get("session_id"))
    return {
        "session_manifest": {
            "session_id": session_id,
            "camera_intrinsics": _nested(session, "camera", "intrinsics"),
            "capture_root": _nested(session, "capture", "root"),
            "images_dir": _nested(session, "capture", "images_dir"),
            "videos_dir": _nested(session, "capture", "videos_dir"),
            "auto_labels": _nested(session, "outputs", "auto_labels"),
            "todo": "Set yolo6d.replay_json_path after automatic keypoint labels or replay predictions are generated.",
        },
        "camera": {
            "source": "d455" if camera_type == "d455" else "hikrobot",
            "color_width": width,
            "color_height": height,
            "fps": fps,
            "enable_depth": False,
            "align_depth_to_color": False,
        },
        "mocap": {
            "enabled": bool(_nested(session, "mocap", "enabled")),
            "mode": "csv",
            "csv_path": _nested(session, "mocap", "csv_path"),
            "camera_rigid_body": _nested(session, "mocap", "camera_rigid"),
            "object_rigid_body": _nested(session, "mocap", "object_rigid"),
            "max_time_diff_s": 0.03,
            "time_offset_s": 0.0,
            "camera_optical_frame": "camera_optical",
            "object_model_frame": "car_model",
            "T_camera_rigid_to_optical": None,
            "T_world_camera_optical": None,
            "T_object_rigid_to_model": {
                "translation_m": [0.0, 0.0, 0.0],
                "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
            },
        },
        "object_model": {
            "label": "car_model",
            "keypoints_mode": "custom",
            "model_json_path": "models/car_custom_keypoints_12_migrated_200xx_exact.json",
            "include_center": False,
        },
        "yolo6d": {
            "backend": "json_replay",
            "conf_threshold": 0.25,
            "replay_json_path": None,
            "model_path": "models/best.pt",
            "replay_timestamp_tolerance_s": 0.05,
            "pnp": {
                "ransac_reproj_threshold_px": 4.0,
                "iterations_count": 100,
                "confidence": 0.99,
                "min_keypoint_score": 0.20,
            },
        },
        "output": {
            "print_json_lines": False,
            "show_window": False,
            "save_csv": f"outputs/replay_runs/{session_id}/pose_results.csv",
        },
    }


def write_replay_config(session: dict[str, Any], paths_config: str | Path | None = None) -> Path:
    """Generate one replay YAML config from a session and return its path."""
    replay_path = resolve_session_paths(session, paths_config)["replay_config"]
    if replay_path is None:
        raise SessionManifestError(f"Session {session.get('session_id')} has no outputs.replay_config")
    replay_path.parent.mkdir(parents=True, exist_ok=True)
    replay_path.write_text(
        yaml.safe_dump(build_replay_config(session), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return replay_path


def _require_mapping(session: dict[str, Any], key: str, required: tuple[str, ...], label: str) -> None:
    value = session.get(key)
    if not isinstance(value, dict):
        raise SessionManifestError(f"{label}.{key} must be a mapping.")
    missing = [field for field in required if field not in value]
    if missing:
        raise SessionManifestError(f"{label}.{key} missing required fields: {missing}")


def _resolve(raw_path: Any, local_paths: LocalPaths | None) -> Path | None:
    return resolve_path(None if raw_path is None else str(raw_path), project_root=PROJECT_ROOT, local_paths=local_paths)


def _nested(mapping: dict[str, Any], section: str, key: str) -> Any:
    value = mapping.get(section, {})
    return value.get(key) if isinstance(value, dict) else None


def _matches_filters(session: dict[str, Any], filters: dict[str, str | None]) -> bool:
    lookup = {
        "speed_level": _nested(session, "motion", "speed_level"),
        "motion_type": _nested(session, "motion", "type"),
        "split": _nested(session, "outputs", "dataset_split"),
        "camera_type": _nested(session, "camera", "type"),
        "lens": _nested(session, "camera", "lens"),
    }
    for key, expected in filters.items():
        if expected is not None and str(lookup.get(key)) != str(expected):
            return False
    return True
