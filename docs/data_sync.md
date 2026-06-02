# Data Sync Workflow

Use `scripts\sync_capture_to_host.py` to copy new capture sessions from a laptop capture folder to the workstation data root. The script preserves the directory structure below `--local-root`, writes `sync_log.txt` inside the destination session folder, and skips existing files by default.

Run commands from the project root:

```powershell
cd D:\Research\YOLO6D_Car
```

## Destination Layout

The destination layout is:

```text
<host-root>\<date>\<experiment>\<relative-source-path>
```

For the workstation:

```text
G:\YOLO6D_Car_Data\captures\2026-05-30\uav_4m_reshoot_d40_bgA_lightOn
```

Supported default file types:

```text
.png .jpg .jpeg .bmp .mp4 .avi .mkv .csv .json .yaml .yml .txt .md
```

## Host G Drive Direct Copy

Use this when running on the workstation and copying from a local/laptop folder already visible to this machine.

```powershell
D:\Envs\yolo6d\python.exe scripts\sync_capture_to_host.py --local-root D:\CaptureData\uav_4m_reshoot_d40_bgA_lightOn --host-root G:\YOLO6D_Car_Data\captures --experiment uav_4m_reshoot_d40_bgA_lightOn --date 2026-05-30
```

## Laptop Z Drive Mapped Copy

Use this when the workstation share is mapped on the laptop as `Z:\captures`.

```powershell
D:\Envs\yolo6d\python.exe scripts\sync_capture_to_host.py --local-root D:\CaptureData\uav_4m_reshoot_d40_bgA_lightOn --host-root Z:\captures --experiment uav_4m_reshoot_d40_bgA_lightOn --date 2026-05-30
```

Expected workstation path if `Z:\captures` maps to `G:\YOLO6D_Car_Data\captures`:

```text
G:\YOLO6D_Car_Data\captures\2026-05-30\uav_4m_reshoot_d40_bgA_lightOn
```

## Dry Run

Dry run prints and logs planned copies without copying data.

```powershell
D:\Envs\yolo6d\python.exe scripts\sync_capture_to_host.py --local-root D:\CaptureData\uav_4m_reshoot_d40_bgA_lightOn --host-root G:\YOLO6D_Car_Data\captures --experiment uav_4m_reshoot_d40_bgA_lightOn --date 2026-05-30 --dry-run
```

## Overwrite Mode

Default behavior is incremental and does not overwrite existing files. Use `--overwrite` only when you intentionally want destination files replaced.

```powershell
D:\Envs\yolo6d\python.exe scripts\sync_capture_to_host.py --local-root D:\CaptureData\uav_4m_reshoot_d40_bgA_lightOn --host-root G:\YOLO6D_Car_Data\captures --experiment uav_4m_reshoot_d40_bgA_lightOn --date 2026-05-30 --overwrite
```

## Verify Mode

Use `--verify` to compare source and destination file sizes after each copied file.

```powershell
D:\Envs\yolo6d\python.exe scripts\sync_capture_to_host.py --local-root D:\CaptureData\uav_4m_reshoot_d40_bgA_lightOn --host-root G:\YOLO6D_Car_Data\captures --experiment uav_4m_reshoot_d40_bgA_lightOn --date 2026-05-30 --verify
```

Overwrite and verify can be combined:

```powershell
D:\Envs\yolo6d\python.exe scripts\sync_capture_to_host.py --local-root D:\CaptureData\uav_4m_reshoot_d40_bgA_lightOn --host-root G:\YOLO6D_Car_Data\captures --experiment uav_4m_reshoot_d40_bgA_lightOn --date 2026-05-30 --overwrite --verify
```

## Local Example Test

This repository includes a tiny source folder for dry-run testing:

```text
data\examples\sync_test
```

PowerShell dry-run test:

```powershell
D:\Envs\yolo6d\python.exe scripts\sync_capture_to_host.py --local-root data\examples\sync_test --host-root data\examples\sync_test_host --experiment demo_sync --date 2026-05-30 --dry-run
```

## Troubleshooting

If `--local-root` does not exist, the script exits with:

```text
ERROR: Local source directory does not exist: ...
```

If `--host-root` does not exist, create or reconnect it first:

```powershell
Test-Path G:\YOLO6D_Car_Data\captures
Test-Path Z:\captures
```

If no supported files are found, check the file extensions or pass custom extensions:

```powershell
D:\Envs\yolo6d\python.exe scripts\sync_capture_to_host.py --local-root D:\CaptureData\session --host-root G:\YOLO6D_Car_Data\captures --experiment session --extensions png csv json txt
```

If permission is denied, check Windows permissions, network share permissions, drive mount state, and whether another process has locked the destination.

