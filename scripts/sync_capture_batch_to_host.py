"""Batch sync capture sessions from the laptop to the host share.

This wrapper keeps the existing single-session sync behavior in
``sync_capture_to_host.py`` and only adds a convenient "sync all sessions"
entry point for field work.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync one or more capture session folders to the host share."
    )
    parser.add_argument(
        "--local-root",
        default=r"D:\CaptureData",
        help=r"Root that contains session folders. Default: D:\CaptureData",
    )
    parser.add_argument(
        "--host-root",
        default=r"Z:\captures",
        help=r"Host captures root. Default: Z:\captures",
    )
    parser.add_argument(
        "--date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Destination date folder. Defaults to today.",
    )
    parser.add_argument(
        "--session",
        action="append",
        help="Session folder name to sync. Repeat this option to sync multiple sessions.",
    )
    parser.add_argument(
        "--include-test",
        action="store_true",
        help="Include folders whose names start with sync_test_.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned copies without copying files.",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Only scan which files are new/duplicated/mismatched for every session.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify copied file sizes after copying.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite destination files if they already exist.",
    )
    return parser.parse_args()


def discover_sessions(local_root: Path, requested_sessions: list[str] | None, include_test: bool) -> list[Path]:
    if not local_root.exists():
        raise FileNotFoundError(f"Local capture root does not exist: {local_root}")
    if not local_root.is_dir():
        raise NotADirectoryError(f"Local capture root is not a directory: {local_root}")

    if requested_sessions:
        sessions = [local_root / name for name in requested_sessions]
    else:
        sessions = [path for path in local_root.iterdir() if path.is_dir()]

    filtered: list[Path] = []
    for session in sorted(sessions, key=lambda item: item.name.lower()):
        if not session.exists():
            raise FileNotFoundError(f"Session folder does not exist: {session}")
        if not session.is_dir():
            raise NotADirectoryError(f"Session path is not a directory: {session}")
        if not include_test and session.name.lower().startswith("sync_test_"):
            continue
        filtered.append(session)
    return filtered


def build_sync_command(
    sync_script: Path,
    session: Path,
    host_root: Path,
    date: str,
    *,
    dry_run: bool,
    plan_only: bool,
    verify: bool,
    overwrite: bool,
) -> list[str]:
    command = [
        sys.executable,
        str(sync_script),
        "--local-root",
        str(session),
        "--host-root",
        str(host_root),
        "--experiment",
        session.name,
        "--date",
        date,
    ]
    if dry_run:
        command.append("--dry-run")
    if plan_only:
        command.append("--plan-only")
    if verify:
        command.append("--verify")
    if overwrite:
        command.append("--overwrite")
    return command


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    sync_script = project_root / "scripts" / "sync_capture_to_host.py"
    local_root = Path(args.local_root)
    host_root = Path(args.host_root)

    if not sync_script.exists():
        raise FileNotFoundError(f"Required sync script is missing: {sync_script}")
    if not host_root.exists():
        raise FileNotFoundError(f"Host root does not exist: {host_root}")

    sessions = discover_sessions(local_root, args.session, args.include_test)
    if not sessions:
        print("No session folders to sync. Use --include-test if you only have sync_test_* folders.")
        return

    print(f"Batch sync start | sessions={len(sessions)} date={args.date} host_root={host_root}")
    for index, session in enumerate(sessions, start=1):
        print(f"\n[{index}/{len(sessions)}] Sync session: {session.name}")
        command = build_sync_command(
            sync_script,
            session,
            host_root,
            args.date,
            dry_run=args.dry_run,
            plan_only=args.plan_only,
            verify=args.verify,
            overwrite=args.overwrite,
        )
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"Sync failed for session {session.name}, exit code={completed.returncode}")

    print("\nBatch sync done.")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, NotADirectoryError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
