# Lab Execution Plan

This document is the real-lab execution package for YOLO6D_Car. It assumes code is on `D:\Research\YOLO6D_Car`, Python is `D:\Envs\yolo6d\python.exe`, and large data goes to `G:\YOLO6D_Car_Data`.

Do not do full-scale training on the first lab pass. The goal is to produce a small, verified real-data loop.

## A. First 10 Minutes

Hardware and room:

- [ ] Intel RealSense D455 connected.
- [ ] Hikrobot MV-CS016-10UC connected.
- [ ] 6mm lens present, clean, and tightened.
- [ ] 8mm lens present, clean, and tightened.
- [ ] Calibration board present.
- [ ] Small car present.
- [ ] Mocap markers attached and visible.
- [ ] Fill light / room light stable.
- [ ] Power / USB / hub / cable routing checked.
- [ ] G drive free space checked.
- [ ] ToDesk / remote connection ready if needed.
- [ ] Sync plan confirmed.

Software:

```powershell
D:\Envs\yolo6d\python.exe scripts\check_project_readiness.py --paths-config configs\paths_local.yaml
```

```powershell
D:\Envs\yolo6d\python.exe scripts\capture_object_samples.py --config configs\object_capture_auto.yaml --paths-config configs\paths_local.yaml --validate-config
```

```powershell
D:\Envs\yolo6d\python.exe scripts\capture_object_samples.py --config configs\object_capture_auto.yaml --paths-config configs\paths_local.yaml --dry-run --max-frames 20
```

Before collecting data, confirm:

- [ ] FzMotion is running.
- [ ] Camera rigid body name is confirmed, for example `hik_rigid` or `d455_rigid`.
- [ ] Car rigid body name is confirmed, for example `car_rigid`.
- [ ] FzMotion CSV will be saved under `G:\YOLO6D_Car_Data\FZmotion_Data\raw_csv`.

## B. Calibration First

Do Hikrobot lens calibration before real Hikrobot data collection. Do not mix 6mm and 8mm intrinsics.

### 6mm

```powershell
D:\Envs\yolo6d\python.exe scripts\calibrate_hik_camera.py --config configs\calibration_hik_6mm.yaml --paths-config configs\paths_local.yaml --validate-config
```

```powershell
D:\Envs\yolo6d\python.exe scripts\calibrate_hik_camera.py --config configs\calibration_hik_6mm.yaml --paths-config configs\paths_local.yaml --mode capture_and_calibrate
```

Expected output:

```text
G:\YOLO6D_Car_Data\outputs\calibration\hik_6mm\camera_intrinsics_hik_6mm.yaml
```

### 8mm

```powershell
D:\Envs\yolo6d\python.exe scripts\calibrate_hik_camera.py --config configs\calibration_hik_8mm.yaml --paths-config configs\paths_local.yaml --validate-config
```

```powershell
D:\Envs\yolo6d\python.exe scripts\calibrate_hik_camera.py --config configs\calibration_hik_8mm.yaml --paths-config configs\paths_local.yaml --mode capture_and_calibrate
```

Expected output:

```text
G:\YOLO6D_Car_Data\outputs\calibration\hik_8mm\camera_intrinsics_hik_8mm.yaml
```

Reprojection error guidance:

- Good: below about `0.5 px`.
- Usable first pass: around `0.5-1.0 px`, if visual undistortion looks stable.
- Suspicious: above `1.0 px`, especially if per-view errors are uneven.

If calibration fails:

- Check square size in config.
- Make sure the correct lens config is used.
- Improve lighting and focus.
- Move the board across center/corners/near/far/tilted poses.
- Do not continue Hikrobot collection with questionable intrinsics unless the goal is only a pipeline smoke test.

## C. First Real Session Plan

Use `configs/real_sessions_first_batch_template.yaml` and replace `TODO_DATE` with the real date before registering final sessions.

| session_id | camera | lens | motion_type | speed | mocap | expected samples | purpose | split |
|---|---|---|---|---|---|---:|---|---|
| `TODO_DATE_car_static_001` | hikrobot | 6mm | static | static | yes | 100-200 | timestamp alignment and PnP baseline | train |
| `TODO_DATE_car_slow_lateral_001` | hikrobot | 6mm | lateral | slow | yes | 200-400 | easy moving sequence | train |
| `TODO_DATE_car_slow_approach_001` | hikrobot | 8mm | approach | slow | yes | 200-400 | scale/depth variation | train |
| `TODO_DATE_car_slow_receding_001` | hikrobot | 8mm | receding | slow | yes | 200-400 | far-distance behavior | val |
| `TODO_DATE_car_rotation_001` | hikrobot | 6mm | rotation | medium | yes | 200-400 | rotation vector stability | train |
| `TODO_DATE_car_fast_lateral_001` | hikrobot | 6mm | lateral | fast | yes | 300-600 | Kalman/reliability stress test | test |
| `TODO_DATE_car_occlusion_001` | hikrobot | 6mm | occlusion | slow | yes | 150-300 | partial visibility test | test |

For the first return to lab, minimum viable target is 3 usable sessions: static, slow lateral, fast lateral.

## D. Standard Session Flow

For each session:

1. Auto capture.
2. Capture quality check.
3. Save and verify FzMotion CSV.
4. Mocap CSV quality check.
5. Register session.
6. Generate mocap labels.
7. Visualize labels.
8. Generate replay config.
9. Run `process_single_session.py`.
10. Prepare dataset after labels are visually verified.

## E. Commands

Generate the full command sheet:

```powershell
D:\Envs\yolo6d\python.exe scripts\print_lab_commands.py --paths-config configs\paths_local.yaml --sessions configs\real_sessions_first_batch_template.yaml --output docs\lab_commands_generated.md
```

Example per-session commands:

```powershell
D:\Envs\yolo6d\python.exe scripts\capture_object_samples.py --config configs\object_capture_auto.yaml --paths-config configs\paths_local.yaml
```

```powershell
D:\Envs\yolo6d\python.exe scripts\check_capture_quality.py --capture-root captures\TODO_DATE\TODO_DATE_car_static_001 --paths-config configs\paths_local.yaml --output-dir results\capture_quality\TODO_DATE_car_static_001 --plot
```

```powershell
D:\Envs\yolo6d\python.exe scripts\check_mocap_csv.py --csv-path FZmotion_Data\raw_csv\TODO_DATE_car_static_001.csv --paths-config configs\paths_local.yaml --camera-rigid hik_rigid --object-rigid car_rigid --output-dir results\mocap_quality\TODO_DATE_car_static_001 --plot
```

```powershell
D:\Envs\yolo6d\python.exe scripts\generate_mocap_labels.py --config outputs\calibration\hik_6mm\camera_intrinsics_hik_6mm.yaml --paths-config configs\paths_local.yaml --samples-dir captures\TODO_DATE\TODO_DATE_car_static_001 --output-dir outputs\auto_labels\TODO_DATE_car_static_001 --csv-path FZmotion_Data\raw_csv\TODO_DATE_car_static_001.csv --save-overlays
```

```powershell
D:\Envs\yolo6d\python.exe scripts\visualize_auto_labels.py --labels-root outputs\auto_labels\TODO_DATE_car_static_001 --images-root captures\TODO_DATE\TODO_DATE_car_static_001\images --paths-config configs\paths_local.yaml --output-dir results\label_visualization\TODO_DATE_car_static_001 --max-samples 100
```

```powershell
D:\Envs\yolo6d\python.exe scripts\process_single_session.py --session-id TODO_DATE_car_static_001 --manifest configs\real_sessions_first_batch_template.yaml --paths-config configs\paths_local.yaml --output-dir results\session_processing\TODO_DATE_car_static_001
```

Dataset and model management:

```powershell
D:\Envs\yolo6d\python.exe scripts\manage_sessions.py --manifest configs\real_sessions_first_batch_template.yaml --paths-config configs\paths_local.yaml --action validate
```

```powershell
D:\Envs\yolo6d\python.exe scripts\manage_datasets.py --manifest configs\dataset_manifest_template.yaml --paths-config configs\paths_local.yaml --action generate-data-yaml
```

```powershell
D:\Envs\yolo6d\python.exe scripts\manage_models.py --registry configs\model_registry_template.yaml --paths-config configs\paths_local.yaml --action print-train-command --model-id car_pose_12pts_v1_yolov8n_pose
```

## F. Backup and Sync

Back up these after the experiment:

- `G:\YOLO6D_Car_Data\captures`
- `G:\YOLO6D_Car_Data\FZmotion_Data`
- `G:\YOLO6D_Car_Data\outputs\auto_labels`
- `G:\YOLO6D_Car_Data\results`
- `G:\YOLO6D_Car_Data\logs`

Laptop-to-host example:

```powershell
D:\Envs\yolo6d\python.exe scripts\sync_capture_to_host.py --local-root D:\CaptureData\TODO_DATE_car_static_001 --host-root G:\YOLO6D_Car_Data\captures --experiment TODO_DATE_car_static_001 --verify
```

Mapped drive example:

```powershell
D:\Envs\yolo6d\python.exe scripts\sync_capture_to_host.py --local-root D:\CaptureData\TODO_DATE_car_static_001 --host-root Z:\captures --experiment TODO_DATE_car_static_001 --verify
```

## G. Do Not Do on Experiment Day

- Do not launch full-scale training before checking overlays.
- Do not train on labels that have not passed visual inspection.
- Do not mix 6mm and 8mm intrinsics.
- Do not collect sessions without metadata.
- Do not commit large files, weights, captures, videos, `.bag`, `.npy`, or `.npz` into Git.
- Do not overwrite calibration results unless intentionally using `--overwrite`.
- Do not keep collecting if mocap rigid body names are wrong.
