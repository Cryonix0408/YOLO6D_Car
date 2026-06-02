# Register Capture Session

`scripts\register_capture_session.py` converts a capture folder into a
`sessions:` entry for the session manifest.

It is useful after auto capture creates:

```text
G:\YOLO6D_Car_Data\captures\<date>\<session_name>\
```

The script reads the folder path and optional `capture_metadata.json`, fills the
standard manifest fields, and can either preview the YAML block or append it to
an existing manifest.

## Dry-Run Preview

```powershell
D:\Envs\yolo6d\python.exe scripts\register_capture_session.py ^
  --capture-root captures\2026-05-30\car_auto_capture_001 ^
  --paths-config configs\paths_local.yaml ^
  --session-id 2026-05-30_car_static_001 ^
  --camera-type d455 ^
  --motion-type static ^
  --speed-level static ^
  --split train ^
  --dry-run
```

This prints:

```yaml
sessions:
  - session_id: ...
```

No file is modified.

## Append to Manifest

```powershell
D:\Envs\yolo6d\python.exe scripts\register_capture_session.py ^
  --capture-root captures\2026-05-30\car_auto_capture_001 ^
  --paths-config configs\paths_local.yaml ^
  --manifest configs\session_manifest_template.yaml ^
  --session-id 2026-05-30_car_static_001 ^
  --camera-type d455 ^
  --motion-type static ^
  --speed-level static ^
  --split train ^
  --append
```

Before writing, the script:

- checks that `session_id` does not already exist,
- validates the generated entry with `session_manifest.py`,
- creates a timestamped manifest backup.

## Useful Options

- `--lens 6mm`
- `--intrinsics outputs\calibration\hik_6mm\camera_intrinsics_hik_6mm.yaml`
- `--mocap-csv FZmotion_Data\raw_csv\<session_id>.csv`
- `--camera-rigid hik_rigid`
- `--object-rigid car_rigid`
- `--occlusion none`
- `--lighting normal`
- `--background lab`

If mocap is not ready yet, leave `--mocap-csv` unset. The script writes TODO
fields and sets `mocap.enabled=false`.

## After Registering

Run:

```powershell
D:\Envs\yolo6d\python.exe scripts\manage_sessions.py ^
  --manifest configs\session_manifest_template.yaml ^
  --paths-config configs\paths_local.yaml ^
  --action validate
```

Then update mocap paths and rigid body names when the FzMotion CSV is available.
