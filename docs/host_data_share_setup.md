# Host Data Share Setup

This guide prepares the workstation as the large-data host for YOLO6D_Car.

Goal:

- Workstation stores large data in `G:\YOLO6D_Car_Data`.
- Capture laptop maps the workstation share as `Z:\`.
- Laptop syncs from `D:\CaptureData\<session>` to `Z:\captures`.
- Final data lands on the host at `G:\YOLO6D_Car_Data\captures\<date>\<session>`.

## 1. Host Directory Layout

On the workstation, create these directories in PowerShell:

```powershell
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data\captures
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data\FZmotion_Data
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data\FZmotion_Data\raw_csv
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data\outputs
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data\outputs\auto_labels
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data\outputs\datasets
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data\outputs\train_runs
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data\outputs\calibration
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data\models
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data\results
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data\logs
```

You can also run:

```powershell
D:\Envs\yolo6d\python.exe scripts\check_host_share_ready.py --create
```

## 2. Share `G:\YOLO6D_Car_Data`

Windows sharing usually needs manual setup:

1. Open File Explorer.
2. Right-click `G:\YOLO6D_Car_Data`.
3. Click **Properties**.
4. Open the **Sharing** tab.
5. Click **Advanced Sharing**.
6. Check **Share this folder**.
7. Set share name to:

```text
YOLO6D_Car_Data
```

8. Click **Permissions**.
9. Grant your Windows user read/change access.
10. For a temporary trusted LAN setup, you may grant `Everyone` read/change access.
11. Confirm and close the dialogs.

Do not expose this share to the public internet.

## 3. Find the Host IP

On the workstation:

```powershell
ipconfig
```

Look for an `IPv4 Address`, for example:

```text
192.168.1.23
```

The share path will be:

```text
\\192.168.1.23\YOLO6D_Car_Data
```

You can also run:

```powershell
D:\Envs\yolo6d\python.exe scripts\check_host_share_ready.py
```

It prints IPv4 candidates and share examples.

## 4. Map `Z:\` on the Capture Laptop

On the capture laptop:

1. Open File Explorer.
2. Open **This PC**.
3. Click **Map network drive**.
4. Choose drive `Z:`.
5. Folder:

```text
\\<HOST_IP>\YOLO6D_Car_Data
```

Example:

```text
\\192.168.1.23\YOLO6D_Car_Data
```

6. Check **Reconnect at sign-in** if useful.
7. Enter workstation credentials if Windows asks.

## 5. Check `Z:\` on the Capture Laptop

```powershell
dir Z:\
dir Z:\captures
```

You should see the workstation data-root folders.

## 6. Small Sync Test

On the capture laptop, create a tiny test session:

```powershell
New-Item -ItemType Directory -Force -Path D:\CaptureData\sync_test_001
"hello sync" | Out-File D:\CaptureData\sync_test_001\test.txt
"sample_id,timestamp" | Out-File D:\CaptureData\sync_test_001\capture_index.csv
```

Dry-run:

```powershell
D:\Envs\yolo6d\python.exe .\scripts\sync_capture_to_host.py ^
  --local-root D:\CaptureData\sync_test_001 ^
  --host-root Z:\captures ^
  --experiment sync_test_001 ^
  --date 2026-05-30 ^
  --dry-run
```

Formal sync:

```powershell
D:\Envs\yolo6d\python.exe .\scripts\sync_capture_to_host.py ^
  --local-root D:\CaptureData\sync_test_001 ^
  --host-root Z:\captures ^
  --experiment sync_test_001 ^
  --date 2026-05-30 ^
  --verify
```

## 7. Check Sync Result on the Host

On the workstation:

```powershell
dir G:\YOLO6D_Car_Data\captures\2026-05-30\sync_test_001
```

Expected files:

- `test.txt`
- `capture_index.csv`
- `sync_log.txt`

## 8. Troubleshooting

Capture laptop cannot access `\\<HOST_IP>\YOLO6D_Car_Data`:

- Confirm the host IP with `ipconfig`.
- Confirm both computers are on the same LAN.
- Try `ping <HOST_IP>` from the laptop.
- Check Windows Network Discovery and File and Printer Sharing.

`Z:\` does not exist:

- Remap the network drive in File Explorer.
- Check that the host is awake and connected.
- Re-enter Windows credentials.

Permission denied:

- Check Advanced Sharing permissions.
- Check NTFS Security tab permissions.
- Temporarily test with `Everyone` read/change on a trusted LAN, then tighten later.

Host and laptop are not on the same LAN:

- Put both on the same Wi-Fi/router or same Ethernet network.
- ToDesk remote control does not mean Windows file sharing is reachable.

Firewall blocks sharing:

- Enable File and Printer Sharing through Windows Defender Firewall for the current private network.
- Make sure the network profile is Private, not Public, when appropriate.

Host sleeps:

- Disable sleep during experiments.
- Keep power connected.

IP address changes:

- Re-run `ipconfig`.
- Remap `Z:\` with the new IP.
- Consider a DHCP reservation later.

Sync is slow:

- Prefer Ethernet for large videos.
- Avoid syncing while training or copying other large files.
- Use `--dry-run` first to estimate file count.

File already exists:

- `sync_capture_to_host.py` does not overwrite by default.
- Use `--overwrite` only when you are sure the destination should be replaced.

Sync interrupted halfway:

- Re-run the same command without `--overwrite`.
- Incremental sync should skip already copied files.
- Use `--verify` to compare copied file sizes.

## 9. Security Advice

- Do not expose `YOLO6D_Car_Data` to the public internet.
- Use this share only on a trusted LAN.
- Do not commit large files to Git.
- Back up important captures and FzMotion CSV regularly.
- After experiments, remove `Everyone` permissions or disable the share if not needed.
