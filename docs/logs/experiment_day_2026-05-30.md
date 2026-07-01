# Experiment Day Checklist - 2026-05-30

- Generated at: `2026-05-30 05:47:08`
- Operator: `Yiyang`
- Location: `lab`
- Objective: Collect small-car 6DoF sessions for calibration, labeling, training, and replay evaluation.

## Path Summary

- Project root: `D:\Research\YOLO6D_Car`
- Data root: `G:\YOLO6D_Car_Data`
- Captures root: `G:\YOLO6D_Car_Data\captures`
- FZmotion root: `G:\YOLO6D_Car_Data\FZmotion_Data`
- Outputs root: `G:\YOLO6D_Car_Data\outputs`
- Results root: `G:\YOLO6D_Car_Data\results`

## 1. Hardware Check

- [ ] RealSense D455 connected and recognized
- [ ] Hikrobot MV-CS016-10UC connected and recognized
- [ ] 6mm lens present, clean, and tightened
- [ ] 8mm lens present, clean, and tightened
- [ ] Chessboard / ChArUco calibration board present
- [ ] Small car object present and marker mounts intact
- [ ] Mocap markers attached and visible
- [ ] Lighting / fill light available and stable
- [ ] Power, USB cables, hubs, and camera mounts checked
- [ ] G drive / capture storage space checked

## 2. Software Check

```powershell
D:\Envs\yolo6d\python.exe scripts\check_project_readiness.py --paths-config configs\paths_local.yaml
```
- [ ] Project readiness check passed

```powershell
D:\Envs\yolo6d\python.exe scripts\capture_object_samples.py --config configs\object_capture_auto.yaml --paths-config configs\paths_local.yaml --validate-config
```
- [ ] Auto capture validate-config passed

```powershell
D:\Envs\yolo6d\python.exe scripts\capture_object_samples.py --config configs\object_capture_auto.yaml --paths-config configs\paths_local.yaml --dry-run --max-frames 20
```
- [ ] Auto capture dry-run passed
- [ ] FzMotion CSV save path set to `G:\YOLO6D_Car_Data\FZmotion_Data\raw_csv`
- [ ] Sync script command reviewed

```powershell
D:\Envs\yolo6d\python.exe scripts\sync_capture_to_host.py --help
```

## 3. Calibration Tasks

### 6mm Hikrobot Lens

```powershell
D:\Envs\yolo6d\python.exe scripts\calibrate_hik_camera.py --config configs\calibration_hik_6mm.yaml --paths-config configs\paths_local.yaml --validate-config
```
- [ ] 6mm calibration validate-config passed
- [ ] 6mm auto calibration completed
- [ ] 6mm intrinsics saved under `G:\YOLO6D_Car_Data\outputs\calibration\hik_6mm`

### 8mm Hikrobot Lens

```powershell
D:\Envs\yolo6d\python.exe scripts\calibrate_hik_camera.py --config configs\calibration_hik_8mm.yaml --paths-config configs\paths_local.yaml --validate-config
```
- [ ] 8mm calibration validate-config passed
- [ ] 8mm auto calibration completed
- [ ] 8mm intrinsics saved under `G:\YOLO6D_Car_Data\outputs\calibration\hik_8mm`

## 4. Planned Capture Sessions

| Done | session_id | motion | speed | camera | lens | camera rigid | object rigid | lighting | background | notes |
|---|---|---|---|---|---|---|---|---|---|---|
| [ ] | `2026-05-30_car_static_001` | static | static | d455 | None | `d455_rigid` | `car_rigid` | normal | lab | Static baseline; confirm mocap/image timestamp alignment. |
| [ ] | `2026-05-30_car_slow_lateral_001` | lateral | slow | hikrobot | 6mm | `hik_rigid` | `car_rigid` | normal | lab | Slow left-right motion for easy tracking. |
| [ ] | `2026-05-30_car_fast_lateral_001` | lateral | fast | hikrobot | 6mm | `hik_rigid` | `car_rigid` | normal | lab | Fast left-right motion for Kalman/reliability ablation. |
| [ ] | `2026-05-30_car_approach_001` | approach | medium | hikrobot | 8mm | `hik_rigid` | `car_rigid` | normal | lab | Car moves toward camera; check scale and PnP stability. |
| [ ] | `2026-05-30_car_receding_001` | receding | medium | hikrobot | 8mm | `hik_rigid` | `car_rigid` | normal | lab | Car moves away from camera; include far-distance samples. |
| [ ] | `2026-05-30_car_rotation_001` | rotation | medium | hikrobot | 6mm | `hik_rigid` | `car_rigid` | normal | lab | Yaw/turning motion; useful for rotation error analysis. |
| [ ] | `2026-05-30_car_occlusion_001` | occlusion | slow | hikrobot | 6mm | `hik_rigid` | `car_rigid` | normal | lab | Controlled partial occlusion; keep occluder visible in metadata notes. |

## 5. Per-Session Notes Template

### 2026-05-30_car_static_001

- [ ] Capture session completed
- [ ] Mocap CSV saved
- [ ] capture_metadata.json checked
- [ ] capture_index.csv checked
- [ ] Lighting/background notes recorded
- [ ] Any failure or unusual motion written below

- Notes:

### 2026-05-30_car_slow_lateral_001

- [ ] Capture session completed
- [ ] Mocap CSV saved
- [ ] capture_metadata.json checked
- [ ] capture_index.csv checked
- [ ] Lighting/background notes recorded
- [ ] Any failure or unusual motion written below

- Notes:

### 2026-05-30_car_fast_lateral_001

- [ ] Capture session completed
- [ ] Mocap CSV saved
- [ ] capture_metadata.json checked
- [ ] capture_index.csv checked
- [ ] Lighting/background notes recorded
- [ ] Any failure or unusual motion written below

- Notes:

### 2026-05-30_car_approach_001

- [ ] Capture session completed
- [ ] Mocap CSV saved
- [ ] capture_metadata.json checked
- [ ] capture_index.csv checked
- [ ] Lighting/background notes recorded
- [ ] Any failure or unusual motion written below

- Notes:

### 2026-05-30_car_receding_001

- [ ] Capture session completed
- [ ] Mocap CSV saved
- [ ] capture_metadata.json checked
- [ ] capture_index.csv checked
- [ ] Lighting/background notes recorded
- [ ] Any failure or unusual motion written below

- Notes:

### 2026-05-30_car_rotation_001

- [ ] Capture session completed
- [ ] Mocap CSV saved
- [ ] capture_metadata.json checked
- [ ] capture_index.csv checked
- [ ] Lighting/background notes recorded
- [ ] Any failure or unusual motion written below

- Notes:

### 2026-05-30_car_occlusion_001

- [ ] Capture session completed
- [ ] Mocap CSV saved
- [ ] capture_metadata.json checked
- [ ] capture_index.csv checked
- [ ] Lighting/background notes recorded
- [ ] Any failure or unusual motion written below

- Notes:

## 6. End-of-Day Checks

- [ ] Run capture quality check for each session
- [ ] Run mocap CSV quality check for each session
- [ ] Register capture sessions into session manifest
- [ ] Sync laptop captures to workstation G drive
- [ ] Backup captures and FzMotion CSV
- [ ] Confirm no large files were committed into Git

Example commands:

```powershell
D:\Envs\yolo6d\python.exe scripts\check_capture_quality.py --capture-root captures\<date>\<session_id> --paths-config configs\paths_local.yaml --output-dir results\capture_quality\<session_id> --plot
D:\Envs\yolo6d\python.exe scripts\check_mocap_csv.py --csv-path FZmotion_Data\raw_csv\<session_id>.csv --paths-config configs\paths_local.yaml --camera-rigid <camera_rigid> --object-rigid car_rigid --output-dir results\mocap_quality\<session_id> --plot
D:\Envs\yolo6d\python.exe scripts\register_capture_session.py --capture-root captures\<date>\<session_id> --paths-config configs\paths_local.yaml --manifest configs\session_manifest_template.yaml --session-id <session_id> --camera-type <camera_type> --motion-type <motion_type> --speed-level <speed_level> --split train --append
```

## 7. Session Coverage Reminder

- [ ] Static baseline captured
- [ ] Slow lateral captured
- [ ] Fast lateral captured
- [ ] Approach captured
- [ ] Receding captured
- [ ] Rotation captured
- [ ] Occlusion captured
