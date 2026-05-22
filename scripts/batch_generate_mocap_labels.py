"""按 manifest 批量执行 Mocap 自动打标签。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


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
    parser.add_argument("--only-enabled", action="store_true", help="Process only sessions with enabled=true. Default behavior is also to skip disabled sessions.")
    return parser.parse_args()


def main() -> None:
    """逐个 session 调用 generate_mocap_labels.py，并汇总批处理结果。"""
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    root_dir = manifest_path.parents[1]

    project_config = _resolve_path(root_dir, manifest.get("project_config", "configs/fzmotion_fixed_camera.yaml"))
    output_root = _resolve_path(root_dir, manifest.get("output_root", "outputs/auto_labels/batch_sessions"))
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
        samples_dir = _resolve_path(root_dir, session.get("samples_dir"))
        csv_path = _resolve_path(root_dir, session.get("csv_path"))
        output_dir = _resolve_path(root_dir, session.get("output_dir")) or (output_root / name)
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

