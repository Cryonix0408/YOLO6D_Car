"""本文件作用：
    将采集端的新文件增量同步到主机数据目录。

在 YOLO6D_Car pipeline 中的位置：
    数据搬运层。采集可以发生在笔记本或采集端，最终大数据应汇总到主机 G 盘。

同步策略：
    扫描 --local-root，只复制目标目录中不存在的文件；默认不覆盖。
    目标目录结构是：

    <host-root>/<date>/<experiment>/<relative-source-path>

注意事项：
    支持 --dry-run 和 --verify。sync_log.txt 会写到目标 experiment 目录。
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_EXTENSIONS = {
    ".avi",
    ".bag",
    ".bmp",
    ".csv",
    ".jpeg",
    ".jpg",
    ".json",
    ".md",
    ".mkv",
    ".mov",
    ".mp4",
    ".png",
    ".txt",
    ".tif",
    ".tiff",
    ".yaml",
    ".yml",
}


def parse_args() -> argparse.Namespace:
    """Parse sync options."""
    parser = argparse.ArgumentParser(
        description="Incrementally sync capture files without overwriting existing host files."
    )
    parser.add_argument(
        "--local-root",
        required=True,
        help="Local capture root, for example D:\\CaptureData\\session_001 or /local/project/data/synthetic/.",
    )
    parser.add_argument(
        "--host-root",
        required=True,
        help="Host destination root, for example G:\\YOLO6D_Car_Data\\captures or Z:\\captures.",
    )
    parser.add_argument(
        "--experiment",
        required=True,
        help="Experiment name used in the destination path.",
    )
    parser.add_argument(
        "--date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Date folder name. Defaults to today's date.",
    )
    parser.add_argument(
        "--extensions",
        nargs="*",
        default=sorted(DEFAULT_EXTENSIONS),
        help="File extensions to sync. Defaults to video/image/CSV/JSON/YAML files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log and print planned copies without copying files.",
    )
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="Validate sync arguments and roots without copying files.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing destination files. Default is incremental copy with no overwrite.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="After copy, verify copied file sizes against source files.",
    )
    return parser.parse_args()


def validate_sync_args(args: argparse.Namespace) -> None:
    """Validate sync roots and report planned destination without copying."""
    local_root = Path(args.local_root).expanduser().resolve()
    host_root = Path(args.host_root).expanduser().resolve()
    extensions = normalize_extensions(args.extensions)
    destination_root = host_root / args.date / args.experiment
    payload = {
        "status": "ok" if local_root.exists() and host_root.exists() else "needs_attention",
        "script": Path(__file__).name,
        "local_root": str(local_root),
        "local_root_exists": local_root.exists(),
        "host_root": str(host_root),
        "host_root_exists": host_root.exists(),
        "destination_root": str(destination_root),
        "extensions": sorted(extensions),
        "copy_required": False,
    }
    print(payload)


def normalize_extensions(raw_extensions: list[str]) -> set[str]:
    """Normalize extensions so both 'png' and '.png' work."""
    normalized: set[str] = set()
    for ext in raw_extensions:
        ext = ext.strip().lower()
        if not ext:
            continue
        normalized.add(ext if ext.startswith(".") else f".{ext}")
    return normalized


def iter_candidate_files(local_root: Path, extensions: set[str]) -> list[Path]:
    """Recursively scan local_root and return files with allowed suffixes."""
    files: list[Path] = []
    for path in local_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in extensions:
            files.append(path)
    return sorted(files)


def build_destination_path(source_file: Path, local_root: Path, destination_root: Path) -> Path:
    """Preserve source relative structure under the destination root."""
    return destination_root / source_file.relative_to(local_root)


def append_log(log_path: Path, message: str) -> None:
    """Append one timestamped line to sync_log.txt."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(f"[{timestamp}] {message}\n")
    except PermissionError as exc:
        raise PermissionError(f"Permission denied while writing sync log: {log_path}") from exc


def verify_file_size(source_file: Path, destination_file: Path) -> None:
    """Raise a clear error if a copied file size differs from the source."""
    source_size = source_file.stat().st_size
    destination_size = destination_file.stat().st_size
    if source_size != destination_size:
        raise RuntimeError(
            "Verification failed: file size mismatch | "
            f"{source_file} ({source_size} bytes) -> {destination_file} ({destination_size} bytes)"
        )


def sync_one_file(
    source_file: Path,
    destination_file: Path,
    log_path: Path,
    *,
    dry_run: bool,
    overwrite: bool,
    verify: bool,
) -> tuple[str, bool]:
    """Copy one file according to incremental/overwrite mode."""
    if destination_file.exists():
        if not overwrite:
            message = f"SKIP destination already exists | {source_file} -> {destination_file}"
            append_log(log_path, message)
            return message, False
        if destination_file.is_dir():
            raise IsADirectoryError(f"Destination already exists as a directory: {destination_file}")

    if dry_run:
        action = "overwrite" if destination_file.exists() and overwrite else "copy"
        message = f"DRY-RUN {action} | {source_file} -> {destination_file}"
        append_log(log_path, message)
        return message, False

    replacing_existing = destination_file.exists()
    try:
        destination_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, destination_file)
    except PermissionError as exc:
        raise PermissionError(f"Permission denied while copying to destination: {destination_file}") from exc

    if verify:
        verify_file_size(source_file, destination_file)

    action = "OVERWRITE" if overwrite and replacing_existing else "COPY"
    message = f"{action} | {source_file} -> {destination_file}"
    append_log(log_path, message)
    return message, True


def validate_roots(local_root: Path, host_root: Path) -> None:
    """Validate source and destination roots before creating session folders."""
    if not local_root.exists():
        raise FileNotFoundError(f"Local source directory does not exist: {local_root}")
    if not local_root.is_dir():
        raise NotADirectoryError(f"Local source path is not a directory: {local_root}")
    if not host_root.exists():
        raise FileNotFoundError(f"Host destination root does not exist: {host_root}")
    if not host_root.is_dir():
        raise NotADirectoryError(f"Host destination root is not a directory: {host_root}")


def main() -> None:
    """Run the incremental sync."""
    args = parse_args()
    if args.validate_config:
        validate_sync_args(args)
        return None
    local_root = Path(args.local_root).expanduser().resolve()
    host_root = Path(args.host_root).expanduser().resolve()
    extensions = normalize_extensions(args.extensions)

    validate_roots(local_root, host_root)

    destination_root = host_root / args.date / args.experiment
    log_path = destination_root / "sync_log.txt"

    append_log(
        log_path,
        f"START local_root={local_root} destination_root={destination_root} "
        f"dry_run={args.dry_run} overwrite={args.overwrite} verify={args.verify}",
    )
    append_log(log_path, f"EXTENSIONS {', '.join(sorted(extensions))}")

    copied = 0
    skipped = 0
    verified = 0
    candidates = iter_candidate_files(local_root, extensions)
    if not candidates:
        raise RuntimeError(
            f"No supported files found under {local_root}. "
            f"Supported extensions: {', '.join(sorted(extensions))}"
        )

    for source_file in candidates:
        destination_file = build_destination_path(source_file, local_root, destination_root)
        result, copied_file = sync_one_file(
            source_file,
            destination_file,
            log_path,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
            verify=args.verify,
        )
        print(result)
        if result.startswith("SKIP"):
            skipped += 1
        elif copied_file:
            copied += 1
            if args.verify:
                verified += 1

    summary = f"DONE scanned={len(candidates)} copied={copied} skipped={skipped} verified={verified} log={log_path}"
    append_log(log_path, summary)
    print(summary)


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, NotADirectoryError, IsADirectoryError, PermissionError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
