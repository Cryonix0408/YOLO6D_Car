# Lab Commands Generated

These commands are printed only. This document does not execute calibration, capture, training, or ablation.

## Global Checks

### Readiness check

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/check_project_readiness.py ^
  --paths-config configs\paths_local.yaml
```

### 6mm calibration validate

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/calibrate_hik_camera.py ^
  --config configs/calibration_hik_6mm.yaml ^
  --paths-config configs\paths_local.yaml ^
  --validate-config
```

### 8mm calibration validate

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/calibrate_hik_camera.py ^
  --config configs/calibration_hik_8mm.yaml ^
  --paths-config configs\paths_local.yaml ^
  --validate-config
```

### 6mm calibration

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/calibrate_hik_camera.py ^
  --config configs/calibration_hik_6mm.yaml ^
  --paths-config configs\paths_local.yaml ^
  --mode capture_and_calibrate
```

### 8mm calibration

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/calibrate_hik_camera.py ^
  --config configs/calibration_hik_8mm.yaml ^
  --paths-config configs\paths_local.yaml ^
  --mode capture_and_calibrate
```

### Manage sessions validate

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/manage_sessions.py ^
  --manifest configs\real_sessions_first_batch_template.yaml ^
  --paths-config configs\paths_local.yaml ^
  --action validate
```

### Generate dataset.yaml

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/manage_datasets.py ^
  --manifest configs/dataset_manifest_template.yaml ^
  --paths-config configs\paths_local.yaml ^
  --action generate-data-yaml
```

### Print train command

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/manage_models.py ^
  --registry configs/model_registry_template.yaml ^
  --paths-config configs\paths_local.yaml ^
  --action print-train-command ^
  --model-id car_pose_12pts_v1_yolov8n_pose
```

## Session `TODO_DATE_car_static_001`

- camera: `hikrobot`
- lens: `6mm`
- motion: `static`
- speed: `static`
- split: `train`

### Auto capture

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/capture_object_samples.py ^
  --config configs/object_capture_auto.yaml ^
  --paths-config configs\paths_local.yaml
```

### Capture quality

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/check_capture_quality.py ^
  --capture-root captures/TODO_DATE/TODO_DATE_car_static_001 ^
  --paths-config configs\paths_local.yaml ^
  --output-dir results/capture_quality/TODO_DATE_car_static_001 ^
  --plot
```

### Mocap CSV quality

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/check_mocap_csv.py ^
  --csv-path FZmotion_Data/raw_csv/TODO_DATE_car_static_001.csv ^
  --paths-config configs\paths_local.yaml ^
  --camera-rigid hik_rigid ^
  --object-rigid car_rigid ^
  --output-dir results/mocap_quality/TODO_DATE_car_static_001 ^
  --plot
```

### Register session

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/register_capture_session.py ^
  --capture-root captures/TODO_DATE/TODO_DATE_car_static_001 ^
  --paths-config configs\paths_local.yaml ^
  --manifest configs\real_sessions_first_batch_template.yaml ^
  --session-id TODO_DATE_car_static_001 ^
  --camera-type hikrobot ^
  --motion-type static ^
  --speed-level static ^
  --split train ^
  --append
```

### Generate mocap labels

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/generate_mocap_labels.py ^
  --config outputs/calibration/hik_6mm/camera_intrinsics_hik_6mm.yaml ^
  --paths-config configs\paths_local.yaml ^
  --samples-dir captures/TODO_DATE/TODO_DATE_car_static_001 ^
  --output-dir outputs/auto_labels/TODO_DATE_car_static_001 ^
  --csv-path FZmotion_Data/raw_csv/TODO_DATE_car_static_001.csv ^
  --save-overlays
```

### Visualize auto labels

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/visualize_auto_labels.py ^
  --labels-root outputs/auto_labels/TODO_DATE_car_static_001 ^
  --images-root captures\TODO_DATE\TODO_DATE_car_static_001\images ^
  --paths-config configs\paths_local.yaml ^
  --output-dir results/label_visualization/TODO_DATE_car_static_001 ^
  --max-samples 100
```

### Process single session

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/process_single_session.py ^
  --session-id TODO_DATE_car_static_001 ^
  --manifest configs\real_sessions_first_batch_template.yaml ^
  --paths-config configs\paths_local.yaml ^
  --output-dir results/session_processing/TODO_DATE_car_static_001
```

### Ablation

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/run_kalman_ablation.py ^
  --config outputs/replay_configs/TODO_DATE_car_static_001.yaml ^
  --paths-config configs\paths_local.yaml ^
  --run-name TODO_DATE_car_static_001 ^
  --max-frames 300 ^
  --plot
```

## Session `TODO_DATE_car_slow_lateral_001`

- camera: `hikrobot`
- lens: `6mm`
- motion: `lateral`
- speed: `slow`
- split: `train`

### Auto capture

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/capture_object_samples.py ^
  --config configs/object_capture_auto.yaml ^
  --paths-config configs\paths_local.yaml
```

### Capture quality

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/check_capture_quality.py ^
  --capture-root captures/TODO_DATE/TODO_DATE_car_slow_lateral_001 ^
  --paths-config configs\paths_local.yaml ^
  --output-dir results/capture_quality/TODO_DATE_car_slow_lateral_001 ^
  --plot
```

### Mocap CSV quality

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/check_mocap_csv.py ^
  --csv-path FZmotion_Data/raw_csv/TODO_DATE_car_slow_lateral_001.csv ^
  --paths-config configs\paths_local.yaml ^
  --camera-rigid hik_rigid ^
  --object-rigid car_rigid ^
  --output-dir results/mocap_quality/TODO_DATE_car_slow_lateral_001 ^
  --plot
```

### Register session

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/register_capture_session.py ^
  --capture-root captures/TODO_DATE/TODO_DATE_car_slow_lateral_001 ^
  --paths-config configs\paths_local.yaml ^
  --manifest configs\real_sessions_first_batch_template.yaml ^
  --session-id TODO_DATE_car_slow_lateral_001 ^
  --camera-type hikrobot ^
  --motion-type lateral ^
  --speed-level slow ^
  --split train ^
  --append
```

### Generate mocap labels

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/generate_mocap_labels.py ^
  --config outputs/calibration/hik_6mm/camera_intrinsics_hik_6mm.yaml ^
  --paths-config configs\paths_local.yaml ^
  --samples-dir captures/TODO_DATE/TODO_DATE_car_slow_lateral_001 ^
  --output-dir outputs/auto_labels/TODO_DATE_car_slow_lateral_001 ^
  --csv-path FZmotion_Data/raw_csv/TODO_DATE_car_slow_lateral_001.csv ^
  --save-overlays
```

### Visualize auto labels

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/visualize_auto_labels.py ^
  --labels-root outputs/auto_labels/TODO_DATE_car_slow_lateral_001 ^
  --images-root captures\TODO_DATE\TODO_DATE_car_slow_lateral_001\images ^
  --paths-config configs\paths_local.yaml ^
  --output-dir results/label_visualization/TODO_DATE_car_slow_lateral_001 ^
  --max-samples 100
```

### Process single session

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/process_single_session.py ^
  --session-id TODO_DATE_car_slow_lateral_001 ^
  --manifest configs\real_sessions_first_batch_template.yaml ^
  --paths-config configs\paths_local.yaml ^
  --output-dir results/session_processing/TODO_DATE_car_slow_lateral_001
```

### Ablation

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/run_kalman_ablation.py ^
  --config outputs/replay_configs/TODO_DATE_car_slow_lateral_001.yaml ^
  --paths-config configs\paths_local.yaml ^
  --run-name TODO_DATE_car_slow_lateral_001 ^
  --max-frames 300 ^
  --plot
```

## Session `TODO_DATE_car_slow_approach_001`

- camera: `hikrobot`
- lens: `8mm`
- motion: `approach`
- speed: `slow`
- split: `train`

### Auto capture

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/capture_object_samples.py ^
  --config configs/object_capture_auto.yaml ^
  --paths-config configs\paths_local.yaml
```

### Capture quality

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/check_capture_quality.py ^
  --capture-root captures/TODO_DATE/TODO_DATE_car_slow_approach_001 ^
  --paths-config configs\paths_local.yaml ^
  --output-dir results/capture_quality/TODO_DATE_car_slow_approach_001 ^
  --plot
```

### Mocap CSV quality

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/check_mocap_csv.py ^
  --csv-path FZmotion_Data/raw_csv/TODO_DATE_car_slow_approach_001.csv ^
  --paths-config configs\paths_local.yaml ^
  --camera-rigid hik_rigid ^
  --object-rigid car_rigid ^
  --output-dir results/mocap_quality/TODO_DATE_car_slow_approach_001 ^
  --plot
```

### Register session

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/register_capture_session.py ^
  --capture-root captures/TODO_DATE/TODO_DATE_car_slow_approach_001 ^
  --paths-config configs\paths_local.yaml ^
  --manifest configs\real_sessions_first_batch_template.yaml ^
  --session-id TODO_DATE_car_slow_approach_001 ^
  --camera-type hikrobot ^
  --motion-type approach ^
  --speed-level slow ^
  --split train ^
  --append
```

### Generate mocap labels

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/generate_mocap_labels.py ^
  --config outputs/calibration/hik_8mm/camera_intrinsics_hik_8mm.yaml ^
  --paths-config configs\paths_local.yaml ^
  --samples-dir captures/TODO_DATE/TODO_DATE_car_slow_approach_001 ^
  --output-dir outputs/auto_labels/TODO_DATE_car_slow_approach_001 ^
  --csv-path FZmotion_Data/raw_csv/TODO_DATE_car_slow_approach_001.csv ^
  --save-overlays
```

### Visualize auto labels

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/visualize_auto_labels.py ^
  --labels-root outputs/auto_labels/TODO_DATE_car_slow_approach_001 ^
  --images-root captures\TODO_DATE\TODO_DATE_car_slow_approach_001\images ^
  --paths-config configs\paths_local.yaml ^
  --output-dir results/label_visualization/TODO_DATE_car_slow_approach_001 ^
  --max-samples 100
```

### Process single session

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/process_single_session.py ^
  --session-id TODO_DATE_car_slow_approach_001 ^
  --manifest configs\real_sessions_first_batch_template.yaml ^
  --paths-config configs\paths_local.yaml ^
  --output-dir results/session_processing/TODO_DATE_car_slow_approach_001
```

### Ablation

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/run_kalman_ablation.py ^
  --config outputs/replay_configs/TODO_DATE_car_slow_approach_001.yaml ^
  --paths-config configs\paths_local.yaml ^
  --run-name TODO_DATE_car_slow_approach_001 ^
  --max-frames 300 ^
  --plot
```

## Session `TODO_DATE_car_slow_receding_001`

- camera: `hikrobot`
- lens: `8mm`
- motion: `receding`
- speed: `slow`
- split: `val`

### Auto capture

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/capture_object_samples.py ^
  --config configs/object_capture_auto.yaml ^
  --paths-config configs\paths_local.yaml
```

### Capture quality

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/check_capture_quality.py ^
  --capture-root captures/TODO_DATE/TODO_DATE_car_slow_receding_001 ^
  --paths-config configs\paths_local.yaml ^
  --output-dir results/capture_quality/TODO_DATE_car_slow_receding_001 ^
  --plot
```

### Mocap CSV quality

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/check_mocap_csv.py ^
  --csv-path FZmotion_Data/raw_csv/TODO_DATE_car_slow_receding_001.csv ^
  --paths-config configs\paths_local.yaml ^
  --camera-rigid hik_rigid ^
  --object-rigid car_rigid ^
  --output-dir results/mocap_quality/TODO_DATE_car_slow_receding_001 ^
  --plot
```

### Register session

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/register_capture_session.py ^
  --capture-root captures/TODO_DATE/TODO_DATE_car_slow_receding_001 ^
  --paths-config configs\paths_local.yaml ^
  --manifest configs\real_sessions_first_batch_template.yaml ^
  --session-id TODO_DATE_car_slow_receding_001 ^
  --camera-type hikrobot ^
  --motion-type receding ^
  --speed-level slow ^
  --split val ^
  --append
```

### Generate mocap labels

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/generate_mocap_labels.py ^
  --config outputs/calibration/hik_8mm/camera_intrinsics_hik_8mm.yaml ^
  --paths-config configs\paths_local.yaml ^
  --samples-dir captures/TODO_DATE/TODO_DATE_car_slow_receding_001 ^
  --output-dir outputs/auto_labels/TODO_DATE_car_slow_receding_001 ^
  --csv-path FZmotion_Data/raw_csv/TODO_DATE_car_slow_receding_001.csv ^
  --save-overlays
```

### Visualize auto labels

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/visualize_auto_labels.py ^
  --labels-root outputs/auto_labels/TODO_DATE_car_slow_receding_001 ^
  --images-root captures\TODO_DATE\TODO_DATE_car_slow_receding_001\images ^
  --paths-config configs\paths_local.yaml ^
  --output-dir results/label_visualization/TODO_DATE_car_slow_receding_001 ^
  --max-samples 100
```

### Process single session

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/process_single_session.py ^
  --session-id TODO_DATE_car_slow_receding_001 ^
  --manifest configs\real_sessions_first_batch_template.yaml ^
  --paths-config configs\paths_local.yaml ^
  --output-dir results/session_processing/TODO_DATE_car_slow_receding_001
```

### Ablation

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/run_kalman_ablation.py ^
  --config outputs/replay_configs/TODO_DATE_car_slow_receding_001.yaml ^
  --paths-config configs\paths_local.yaml ^
  --run-name TODO_DATE_car_slow_receding_001 ^
  --max-frames 300 ^
  --plot
```

## Session `TODO_DATE_car_rotation_001`

- camera: `hikrobot`
- lens: `6mm`
- motion: `rotation`
- speed: `medium`
- split: `train`

### Auto capture

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/capture_object_samples.py ^
  --config configs/object_capture_auto.yaml ^
  --paths-config configs\paths_local.yaml
```

### Capture quality

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/check_capture_quality.py ^
  --capture-root captures/TODO_DATE/TODO_DATE_car_rotation_001 ^
  --paths-config configs\paths_local.yaml ^
  --output-dir results/capture_quality/TODO_DATE_car_rotation_001 ^
  --plot
```

### Mocap CSV quality

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/check_mocap_csv.py ^
  --csv-path FZmotion_Data/raw_csv/TODO_DATE_car_rotation_001.csv ^
  --paths-config configs\paths_local.yaml ^
  --camera-rigid hik_rigid ^
  --object-rigid car_rigid ^
  --output-dir results/mocap_quality/TODO_DATE_car_rotation_001 ^
  --plot
```

### Register session

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/register_capture_session.py ^
  --capture-root captures/TODO_DATE/TODO_DATE_car_rotation_001 ^
  --paths-config configs\paths_local.yaml ^
  --manifest configs\real_sessions_first_batch_template.yaml ^
  --session-id TODO_DATE_car_rotation_001 ^
  --camera-type hikrobot ^
  --motion-type rotation ^
  --speed-level medium ^
  --split train ^
  --append
```

### Generate mocap labels

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/generate_mocap_labels.py ^
  --config outputs/calibration/hik_6mm/camera_intrinsics_hik_6mm.yaml ^
  --paths-config configs\paths_local.yaml ^
  --samples-dir captures/TODO_DATE/TODO_DATE_car_rotation_001 ^
  --output-dir outputs/auto_labels/TODO_DATE_car_rotation_001 ^
  --csv-path FZmotion_Data/raw_csv/TODO_DATE_car_rotation_001.csv ^
  --save-overlays
```

### Visualize auto labels

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/visualize_auto_labels.py ^
  --labels-root outputs/auto_labels/TODO_DATE_car_rotation_001 ^
  --images-root captures\TODO_DATE\TODO_DATE_car_rotation_001\images ^
  --paths-config configs\paths_local.yaml ^
  --output-dir results/label_visualization/TODO_DATE_car_rotation_001 ^
  --max-samples 100
```

### Process single session

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/process_single_session.py ^
  --session-id TODO_DATE_car_rotation_001 ^
  --manifest configs\real_sessions_first_batch_template.yaml ^
  --paths-config configs\paths_local.yaml ^
  --output-dir results/session_processing/TODO_DATE_car_rotation_001
```

### Ablation

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/run_kalman_ablation.py ^
  --config outputs/replay_configs/TODO_DATE_car_rotation_001.yaml ^
  --paths-config configs\paths_local.yaml ^
  --run-name TODO_DATE_car_rotation_001 ^
  --max-frames 300 ^
  --plot
```

## Session `TODO_DATE_car_fast_lateral_001`

- camera: `hikrobot`
- lens: `6mm`
- motion: `lateral`
- speed: `fast`
- split: `test`

### Auto capture

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/capture_object_samples.py ^
  --config configs/object_capture_auto.yaml ^
  --paths-config configs\paths_local.yaml
```

### Capture quality

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/check_capture_quality.py ^
  --capture-root captures/TODO_DATE/TODO_DATE_car_fast_lateral_001 ^
  --paths-config configs\paths_local.yaml ^
  --output-dir results/capture_quality/TODO_DATE_car_fast_lateral_001 ^
  --plot
```

### Mocap CSV quality

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/check_mocap_csv.py ^
  --csv-path FZmotion_Data/raw_csv/TODO_DATE_car_fast_lateral_001.csv ^
  --paths-config configs\paths_local.yaml ^
  --camera-rigid hik_rigid ^
  --object-rigid car_rigid ^
  --output-dir results/mocap_quality/TODO_DATE_car_fast_lateral_001 ^
  --plot
```

### Register session

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/register_capture_session.py ^
  --capture-root captures/TODO_DATE/TODO_DATE_car_fast_lateral_001 ^
  --paths-config configs\paths_local.yaml ^
  --manifest configs\real_sessions_first_batch_template.yaml ^
  --session-id TODO_DATE_car_fast_lateral_001 ^
  --camera-type hikrobot ^
  --motion-type lateral ^
  --speed-level fast ^
  --split test ^
  --append
```

### Generate mocap labels

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/generate_mocap_labels.py ^
  --config outputs/calibration/hik_6mm/camera_intrinsics_hik_6mm.yaml ^
  --paths-config configs\paths_local.yaml ^
  --samples-dir captures/TODO_DATE/TODO_DATE_car_fast_lateral_001 ^
  --output-dir outputs/auto_labels/TODO_DATE_car_fast_lateral_001 ^
  --csv-path FZmotion_Data/raw_csv/TODO_DATE_car_fast_lateral_001.csv ^
  --save-overlays
```

### Visualize auto labels

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/visualize_auto_labels.py ^
  --labels-root outputs/auto_labels/TODO_DATE_car_fast_lateral_001 ^
  --images-root captures\TODO_DATE\TODO_DATE_car_fast_lateral_001\images ^
  --paths-config configs\paths_local.yaml ^
  --output-dir results/label_visualization/TODO_DATE_car_fast_lateral_001 ^
  --max-samples 100
```

### Process single session

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/process_single_session.py ^
  --session-id TODO_DATE_car_fast_lateral_001 ^
  --manifest configs\real_sessions_first_batch_template.yaml ^
  --paths-config configs\paths_local.yaml ^
  --output-dir results/session_processing/TODO_DATE_car_fast_lateral_001
```

### Ablation

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/run_kalman_ablation.py ^
  --config outputs/replay_configs/TODO_DATE_car_fast_lateral_001.yaml ^
  --paths-config configs\paths_local.yaml ^
  --run-name TODO_DATE_car_fast_lateral_001 ^
  --max-frames 300 ^
  --plot
```

## Session `TODO_DATE_car_occlusion_001`

- camera: `hikrobot`
- lens: `6mm`
- motion: `occlusion`
- speed: `slow`
- split: `test`

### Auto capture

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/capture_object_samples.py ^
  --config configs/object_capture_auto.yaml ^
  --paths-config configs\paths_local.yaml
```

### Capture quality

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/check_capture_quality.py ^
  --capture-root captures/TODO_DATE/TODO_DATE_car_occlusion_001 ^
  --paths-config configs\paths_local.yaml ^
  --output-dir results/capture_quality/TODO_DATE_car_occlusion_001 ^
  --plot
```

### Mocap CSV quality

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/check_mocap_csv.py ^
  --csv-path FZmotion_Data/raw_csv/TODO_DATE_car_occlusion_001.csv ^
  --paths-config configs\paths_local.yaml ^
  --camera-rigid hik_rigid ^
  --object-rigid car_rigid ^
  --output-dir results/mocap_quality/TODO_DATE_car_occlusion_001 ^
  --plot
```

### Register session

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/register_capture_session.py ^
  --capture-root captures/TODO_DATE/TODO_DATE_car_occlusion_001 ^
  --paths-config configs\paths_local.yaml ^
  --manifest configs\real_sessions_first_batch_template.yaml ^
  --session-id TODO_DATE_car_occlusion_001 ^
  --camera-type hikrobot ^
  --motion-type occlusion ^
  --speed-level slow ^
  --split test ^
  --append
```

### Generate mocap labels

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/generate_mocap_labels.py ^
  --config outputs/calibration/hik_6mm/camera_intrinsics_hik_6mm.yaml ^
  --paths-config configs\paths_local.yaml ^
  --samples-dir captures/TODO_DATE/TODO_DATE_car_occlusion_001 ^
  --output-dir outputs/auto_labels/TODO_DATE_car_occlusion_001 ^
  --csv-path FZmotion_Data/raw_csv/TODO_DATE_car_occlusion_001.csv ^
  --save-overlays
```

### Visualize auto labels

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/visualize_auto_labels.py ^
  --labels-root outputs/auto_labels/TODO_DATE_car_occlusion_001 ^
  --images-root captures\TODO_DATE\TODO_DATE_car_occlusion_001\images ^
  --paths-config configs\paths_local.yaml ^
  --output-dir results/label_visualization/TODO_DATE_car_occlusion_001 ^
  --max-samples 100
```

### Process single session

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/process_single_session.py ^
  --session-id TODO_DATE_car_occlusion_001 ^
  --manifest configs\real_sessions_first_batch_template.yaml ^
  --paths-config configs\paths_local.yaml ^
  --output-dir results/session_processing/TODO_DATE_car_occlusion_001
```

### Ablation

```powershell
D:\Envs\yolo6d\python.exe ^
  scripts/run_kalman_ablation.py ^
  --config outputs/replay_configs/TODO_DATE_car_occlusion_001.yaml ^
  --paths-config configs\paths_local.yaml ^
  --run-name TODO_DATE_car_occlusion_001 ^
  --max-frames 300 ^
  --plot
```

