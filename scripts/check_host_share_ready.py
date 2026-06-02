"""Check whether the workstation data root is ready for laptop sync.

This script is host-side only. It checks the expected G-drive directory layout,
free disk space, local IPv4 candidates, and prints the network share/mapping
commands that the capture laptop should use.
"""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
from pathlib import Path


DATA_ROOT = Path(r"G:\YOLO6D_Car_Data")
REQUIRED_DIRS = [
    DATA_ROOT,
    DATA_ROOT / "captures",
    DATA_ROOT / "FZmotion_Data",
    DATA_ROOT / "FZmotion_Data" / "raw_csv",
    DATA_ROOT / "outputs",
    DATA_ROOT / "outputs" / "auto_labels",
    DATA_ROOT / "outputs" / "datasets",
    DATA_ROOT / "outputs" / "train_runs",
    DATA_ROOT / "outputs" / "calibration",
    DATA_ROOT / "models",
    DATA_ROOT / "results",
    DATA_ROOT / "logs",
]


def parse_args() -> argparse.Namespace:
    """Parse host-share readiness options."""
    parser = argparse.ArgumentParser(description="Check YOLO6D_Car host data-share readiness.")
    parser.add_argument("--data-root", default=str(DATA_ROOT), help="Host data root. Default: G:\\YOLO6D_Car_Data")
    parser.add_argument("--create", action="store_true", help="Create missing required directories.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only.")
    return parser.parse_args()


def ipv4_candidates() -> list[str]:
    """Return non-loopback IPv4 addresses likely useful for Windows file sharing."""
    candidates: set[str] = set()

    try:
        hostname = socket.gethostname()
        for item in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = item[4][0]
            if not ip.startswith("127."):
                candidates.add(ip)
    except OSError:
        pass

    try:
        completed = subprocess.run(["ipconfig"], text=True, capture_output=True, check=False)
        for line in completed.stdout.splitlines():
            if "IPv4" not in line:
                continue
            if ":" not in line:
                continue
            ip = line.split(":", 1)[1].strip()
            if ip and not ip.startswith("127."):
                candidates.add(ip)
    except OSError:
        pass

    return sorted(candidates)


def bytes_to_gib(value: int) -> float:
    """Convert bytes to GiB."""
    return round(value / (1024**3), 2)


def build_required_dirs(data_root: Path) -> list[Path]:
    """Build required directory list for a custom data root."""
    return [
        data_root,
        data_root / "captures",
        data_root / "FZmotion_Data",
        data_root / "FZmotion_Data" / "raw_csv",
        data_root / "outputs",
        data_root / "outputs" / "auto_labels",
        data_root / "outputs" / "datasets",
        data_root / "outputs" / "train_runs",
        data_root / "outputs" / "calibration",
        data_root / "models",
        data_root / "results",
        data_root / "logs",
    ]


def main() -> int:
    """Check host directory layout, disk space, IPv4 candidates, and share hints."""
    args = parse_args()
    data_root = Path(args.data_root)
    required_dirs = build_required_dirs(data_root)

    created: list[str] = []
    if args.create:
        for directory in required_dirs:
            directory.mkdir(parents=True, exist_ok=True)
            created.append(str(directory))

    findings = [{"path": str(directory), "exists": directory.exists(), "is_dir": directory.is_dir()} for directory in required_dirs]
    missing = [item["path"] for item in findings if not item["is_dir"]]

    disk = None
    drive_root = Path(data_root.anchor or str(data_root))
    if drive_root.exists():
        usage = shutil.disk_usage(drive_root)
        disk = {
            "drive": str(drive_root),
            "total_gib": bytes_to_gib(usage.total),
            "used_gib": bytes_to_gib(usage.used),
            "free_gib": bytes_to_gib(usage.free),
        }

    ips = ipv4_candidates()
    share_examples = [fr"\\{ip}\YOLO6D_Car_Data" for ip in ips]
    sync_test_commands = [
        r"D:\Envs\yolo6d\python.exe .\scripts\sync_capture_to_host.py ^",
        r"  --local-root D:\CaptureData\sync_test_001 ^",
        r"  --host-root Z:\captures ^",
        r"  --experiment sync_test_001 ^",
        r"  --date 2026-05-30 ^",
        r"  --dry-run",
    ]

    payload = {
        "data_root": str(data_root),
        "created": created,
        "findings": findings,
        "missing": missing,
        "disk": disk,
        "ipv4_candidates": ips,
        "share_examples": share_examples,
        "laptop_mapping": r"Z:\ -> \\<HOST_IP>\YOLO6D_Car_Data",
        "laptop_sync_test_command": "\n".join(sync_test_commands),
    }

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if not missing else 2

    print("YOLO6D_Car host share readiness")
    print("=" * 36)
    print(f"Data root: {data_root}")
    print("")
    print("Required directories:")
    for item in findings:
        status = "OK" if item["is_dir"] else "MISSING"
        print(f"  [{status}] {item['path']}")
    if created:
        print("")
        print("Created directories:")
        for path in created:
            print(f"  {path}")

    print("")
    if disk is None:
        print("Disk space: unavailable; drive root does not exist or is not accessible.")
    else:
        print(f"Disk space on {disk['drive']}: total={disk['total_gib']} GiB, used={disk['used_gib']} GiB, free={disk['free_gib']} GiB")

    print("")
    print("Host IPv4 candidates:")
    if ips:
        for ip in ips:
            print(f"  {ip}")
    else:
        print("  None found. Run ipconfig manually and look for IPv4 Address.")

    print("")
    print("Suggested Windows share path:")
    if share_examples:
        for share in share_examples:
            print(f"  {share}")
    else:
        print(r"  \\<HOST_IP>\YOLO6D_Car_Data")

    print("")
    print("Capture laptop network drive mapping:")
    print(r"  Z:\ -> \\<HOST_IP>\YOLO6D_Car_Data")
    print("")
    print("Laptop dry-run sync test command:")
    print("\n".join(sync_test_commands))
    print("")
    print("Manual share setup reminder:")
    print(r"  Right-click G:\YOLO6D_Car_Data -> Properties -> Sharing -> Advanced Sharing")
    print("  Share name: YOLO6D_Car_Data")
    print("  Permissions: grant your Windows user, or temporarily Everyone, read/change access on a trusted LAN.")
    print("")
    if missing:
        print("Missing directories remain. Run this script with --create or create them manually.")
        return 2
    print("Status: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
