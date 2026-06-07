"""按 manifest 批量执行 Mocap 自动打标签。"""

from __future__ import annotations

# 读代码提示：
# 这是 generate_mocap_labels.py 的批处理外壳。它按 manifest/session 列表生成命令，
# 适合真实数据变多之后批量打标签。第一批真实数据建议先用单 session 跑通并检查 overlay，
# 再使用批处理。

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.path_utils import load_local_paths, resolve_path


def _resolve_path(root: Path, raw: str | None) -> Path | None:
    """把 manifest 里的相对路径统一解析到项目根目录下。"""
    if raw is None:
        return None
    raw = str(raw).strip()
    if raw == "":
        return None
    path = Path(raw)
    return path if path.is_absolute() else (root / path)


def parse_args() -> argparse.Namespace:
    """定义批处理入口参数，只要求传入多 session manifest。"""
    parser = argparse.ArgumentParser(description="Batch-generate mocap labels from a multi-session YAML manifest.")
    parser.add_argument("--manifest", required=True, help="Path to the multi-session YAML manifest.")
    parser.add_argument("--paths-config", default=None, help="Optional local paths YAML, e.g. configs/paths_local.yaml.")
    parser.add_argument("--validate-config", action="store_true", help="Validate manifest paths without processing sessions.")
    parser.add_argument("--only-enabled", action="store_true", help="Process only sessions with enabled=true. Default behavior is also to skip disabled sessions.")
    return parser.parse_args()


def validate_batch_manifest(args: argparse.Namespace) -> None:
    """Validate batch label manifest without reading capture data or mocap CSVs."""
    manifest_path = Path(args.manifest).resolve()
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    root_dir = manifest_path.parents[1]
    local_paths = load_local_paths(args.paths_config) if args.paths_config else None
    project_config = resolve_path(
        manifest.get("project_config", "configs/fzmotion_fixed_camera_current_rigids.yaml"),
        project_root=root_dir,
        local_paths=None,
    )
    output_root = resolve_path(manifest.get("output_root", "outputs/auto_labels/batch_sessions"), project_root=root_dir, local_paths=local_paths)
    sessions = manifest.get("sessions", [])
    resolved_sessions = []
    for session in sessions:
        if not bool(session.get("enabled", False)):
            continue
        samples_dir = resolve_path(session.get("samples_dir"), project_root=root_dir, local_paths=local_paths)
        csv_path = resolve_path(session.get("csv_path"), project_root=root_dir, local_paths=local_paths)
        resolved_sessions.append(
            {
                "name": session.get("name"),
                "samples_dir": None if samples_dir is None else str(samples_dir),
                "samples_dir_exists": None if samples_dir is None else samples_dir.exists(),
                "csv_path": None if csv_path is None else str(csv_path),
                "csv_exists": None if csv_path is None else csv_path.exists(),
            }
        )
    print(
        json.dumps(
            {
                "status": "ok",
                "script": Path(__file__).name,
                "manifest": str(manifest_path),
                "project_config": str(project_config),
                "project_config_exists": project_config.exists() if project_config is not None else False,
                "output_root": str(output_root),
                "enabled_sessions": len(resolved_sessions),
                "sessions": resolved_sessions[:5],
                "large_data_required": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> None:
    """逐个 session 调用 generate_mocap_labels.py，并汇总批处理结果。"""
    args = parse_args()
    if args.validate_config:
        validate_batch_manifest(args)
        return None
    manifest_path = Path(args.manifest).resolve()
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    root_dir = manifest_path.parents[1]
    local_paths = load_local_paths(args.paths_config) if args.paths_config else None

    project_config = resolve_path(
        manifest.get("project_config", "configs/fzmotion_fixed_camera_current_rigids.yaml"),
        project_root=root_dir,
        local_paths=None,
    )
    output_root = resolve_path(manifest.get("output_root", "outputs/auto_labels/batch_sessions"), project_root=root_dir, local_paths=local_paths)
    class_id = int(manifest.get("class_id", 0))
    min_inframe_keypoints = int(manifest.get("min_inframe_keypoints", 4))
    save_overlays = bool(manifest.get("save_overlays", True))
    sessions = manifest.get("sessions", [])
    if not sessions:
        raise RuntimeError(f"No sessions found in manifest: {manifest_path}")

    output_root.mkdir(parents=True, exist_ok=True)
    session_summaries: list[dict[str, object]] = []

    for session in sessions:
        # manifest 可以保留暂时不用的 session；这里只处理显式 enabled 的条目。
        enabled = bool(session.get("enabled", False))
        if not enabled:
            continue

        name = str(session["name"])
        samples_dir = resolve_path(session.get("samples_dir"), project_root=root_dir, local_paths=local_paths)
        csv_path = resolve_path(session.get("csv_path"), project_root=root_dir, local_paths=local_paths)
        output_dir = resolve_path(session.get("output_dir"), project_root=root_dir, local_paths=local_paths) or (output_root / name)
        if samples_dir is None:
            raise RuntimeError(f"Session '{name}' is missing samples_dir")
        if csv_path is None:
            raise RuntimeError(f"Session '{name}' is missing csv_path")

        # 这里用子进程而不是直接 import main，便于每个 session 独立打印进度和失败原因。
        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "generate_mocap_labels.py"),
            "--config",
            str(project_config),
            "--samples-dir",
            str(samples_dir),
            "--csv-path",
            str(csv_path),
            "--output-dir",
            str(output_dir),
            "--class-id",
            str(class_id),
            "--min-inframe-keypoints",
            str(min_inframe_keypoints),
        ]
        if args.paths_config:
            cmd.extend(["--paths-config", str(args.paths_config)])
        if save_overlays:
            cmd.append("--save-overlays")

        # 打印 JSON 便于之后从日志里复现实验命令。
        print(json.dumps({"running": name, "cmd": cmd}, ensure_ascii=False))
        subprocess.run(cmd, check=True)
        session_summaries.append(
            {
                "name": name,
                "samples_dir": str(samples_dir),
                "csv_path": str(csv_path),
                "output_dir": str(output_dir),
                "distance_m": session.get("distance_m"),
                "background": session.get("background"),
                "light": session.get("light"),
            }
        )

    summary = {
        "manifest": str(manifest_path),
        "project_config": str(project_config),
        "output_root": str(output_root),
        "num_processed_sessions": len(session_summaries),
        "sessions": session_summaries,
    }
    summary_path = output_root / "batch_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
