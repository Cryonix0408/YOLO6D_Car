# Experiment Day Checklist Workflow

Use `scripts/generate_experiment_day_checklist.py` before going to the lab. It creates a printable Markdown checklist for hardware, software, calibration, capture sessions, and end-of-day backup checks.

The script does not collect data, train models, or generate large files.

## Planned Sessions Template

Edit:

```text
configs\planned_sessions_template.yaml
```

Each planned session can include:

- `session_id`
- `motion_type`
- `speed_level`
- `camera_type`
- `lens`
- `camera_rigid`
- `object_rigid`
- `lighting`
- `background`
- `notes`

The script also accepts a `sessions:` list if you want to reuse a session-manifest-like file.

## Generate Checklist

```powershell
D:\Envs\yolo6d\python.exe scripts\generate_experiment_day_checklist.py `
  --date 2026-05-30 `
  --planned-sessions configs\planned_sessions_template.yaml `
  --paths-config configs\paths_local.yaml `
  --output docs\experiment_day_2026-05-30.md
```

## What It Includes

- Hardware checklist:
  D455, Hikrobot camera, 6mm / 8mm lens, calibration board, small car, mocap markers, lighting, power, USB, and storage.
- Software checklist:
  readiness check, validate-config, auto capture dry-run, mocap CSV path, and sync script.
- Calibration tasks:
  6mm and 8mm Hikrobot lens checks.
- Planned session table:
  static, slow lateral, fast lateral, approach, receding, rotation, and occlusion sessions.
- Per-session notes blocks.
- End-of-day checks:
  capture quality, mocap quality, session registration, sync, and backup.

## After the Lab Day

For each completed session, run:

```powershell
D:\Envs\yolo6d\python.exe scripts\check_capture_quality.py --capture-root captures\<date>\<session_id> --paths-config configs\paths_local.yaml --output-dir results\capture_quality\<session_id> --plot
```

```powershell
D:\Envs\yolo6d\python.exe scripts\check_mocap_csv.py --csv-path FZmotion_Data\raw_csv\<session_id>.csv --paths-config configs\paths_local.yaml --camera-rigid <camera_rigid> --object-rigid car_rigid --output-dir results\mocap_quality\<session_id> --plot
```

Then register the session into the session manifest and continue with single-session processing.
## Code Reading Notes

- checklist 生成器是 `scripts/generate_experiment_day_checklist.py`。
- 它只写 Markdown，不连接硬件，不采集数据。
- 计划 session 模板是 `configs/planned_sessions_template.yaml`。
- 真实执行命令包见 `docs/lab_execution_plan.md` 和 `docs/lab_commands_generated.md`。
