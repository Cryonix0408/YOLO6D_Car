# Full Pipeline Checklist

Project root: `D:\Research\YOLO6D_Car`

Python: `D:\Envs\yolo6d\python.exe`

Data root: `G:\YOLO6D_Car_Data`

This checklist is for building the full program skeleton first, then adding real data later. Historical docs may still contain older paths; prefer the G-drive commands here.

| Stage | Script entry | Config | Inputs | Outputs | Hardware | G data | Validate command | Formal command |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Path management | `src/yolo6d_car/path_utils.py` | `configs/paths_local.yaml` | D/G roots | Resolved `Path` objects | No | No | `D:\Envs\yolo6d\python.exe scripts\check_project_readiness.py --paths-config configs\paths_local.yaml` | Used by other scripts with `--paths-config configs\paths_local.yaml` |
| Hik camera calibration | `scripts/calibrate_hik_camera.py` | `configs/calibration_hik_6mm.yaml`, `configs/calibration_hik_8mm.yaml` | Chessboard images from Hik camera | `G:\YOLO6D_Car_Data\outputs\calibration\hik_*\camera_intrinsics_*.yaml` | Yes for capture | Yes for outputs | `D:\Envs\yolo6d\python.exe scripts\calibrate_hik_camera.py --config configs\calibration_hik_6mm.yaml --paths-config configs\paths_local.yaml --validate-config` | `D:\Envs\yolo6d\python.exe scripts\calibrate_hik_camera.py --config configs\calibration_hik_6mm.yaml --paths-config configs\paths_local.yaml --mode capture_and_calibrate` |
| RealSense D455 capture | `scripts/capture_object_samples.py`, `scripts/capture_board_samples.py` | `configs/object_capture_gdrive.yaml`, `configs/board_capture_gdrive.yaml` | D455 frames | `G:\YOLO6D_Car_Data\outputs\object_capture\<session>` | Yes | Yes | `D:\Envs\yolo6d\python.exe scripts\capture_object_samples.py --config configs\object_capture_gdrive.yaml --paths-config configs\paths_local.yaml --validate-config` | `D:\Envs\yolo6d\python.exe scripts\capture_object_samples.py --config configs\object_capture_gdrive.yaml --paths-config configs\paths_local.yaml` |
| FzMotion CSV reading | `src/yolo6d_car/mocap/csv_provider.py` | Project YAML `mocap.csv_path` | `FZmotion_Data\*.csv` | Pose lookup provider | No | Yes for real CSV | `D:\Envs\yolo6d\python.exe scripts\generate_mocap_labels.py --config configs\fzmotion_fixed_camera_current_rigids_gdrive.yaml --paths-config configs\paths_local.yaml --validate-config` | Used by labeling and replay when mocap is enabled |
| Auto 2D keypoint labels | `scripts/generate_mocap_labels.py`, `scripts/batch_generate_mocap_labels.py` | `configs/fzmotion_fixed_camera_current_rigids_gdrive.yaml`, `configs/uav_4m_20_sessions_gdrive.yaml` | Captures, mocap CSV, object model | `outputs\auto_labels\...` | No | Yes | `D:\Envs\yolo6d\python.exe scripts\batch_generate_mocap_labels.py --manifest configs\uav_4m_20_sessions_gdrive.yaml --paths-config configs\paths_local.yaml --validate-config` | `D:\Envs\yolo6d\python.exe scripts\batch_generate_mocap_labels.py --manifest configs\uav_4m_20_sessions_gdrive.yaml --paths-config configs\paths_local.yaml` |
| YOLO Pose dataset | `scripts/prepare_yolo_pose_dataset.py` | CLI args | Auto-label dirs | `outputs\datasets\<name>\dataset.yaml` | No | Yes | `D:\Envs\yolo6d\python.exe scripts\prepare_yolo_pose_dataset.py --paths-config configs\paths_local.yaml --validate-config --out-dir outputs\datasets\validate_placeholder` | `D:\Envs\yolo6d\python.exe scripts\prepare_yolo_pose_dataset.py --paths-config configs\paths_local.yaml --auto-label-dir outputs\auto_labels\uav_4m_20_sessions_batch\d40_bgA_lightOn --out-dir outputs\datasets\uav_4m_20_sessions_pose` |
| YOLO Pose training | `scripts/train_ultralytics_pose.py` | CLI args | `dataset.yaml`, initial model | `outputs\train_runs\<run>\weights\best.pt` | GPU recommended | Yes | `D:\Envs\yolo6d\python.exe scripts\train_ultralytics_pose.py --paths-config configs\paths_local.yaml --validate-config --dataset outputs\datasets\uav_4m_20_sessions_pose\dataset.yaml --model yolo11n-pose.pt` | `D:\Envs\yolo6d\python.exe scripts\train_ultralytics_pose.py --paths-config configs\paths_local.yaml --dataset outputs\datasets\uav_4m_20_sessions_pose\dataset.yaml --model yolo11n-pose.pt --device 0 --project outputs\train_runs --name uav_4m_20sessions_pose_v1` |
| PnP 6DoF replay | `scripts/smoke_replay_pipeline.py` | `configs/local_smoke_replay.yaml`, `configs/local_smoke_replay_gdrive.yaml` | Example replay JSON | Terminal JSON / optional CSV | No | No for local smoke | `D:\Envs\yolo6d\python.exe scripts\smoke_replay_pipeline.py --config configs\local_smoke_replay.yaml --validate-config` | `D:\Envs\yolo6d\python.exe scripts\smoke_replay_pipeline.py --config configs\local_smoke_replay.yaml --max-frames 3` |
| Live realtime pose | `scripts/run_live_pose.py` | `configs/fzmotion_fixed_camera_live_v1_gdrive.yaml` | Camera frames, trained `best.pt` | Realtime pose stream / CSV | Yes | Yes for weights/logs | `D:\Envs\yolo6d\python.exe scripts\run_live_pose.py --config configs\fzmotion_fixed_camera_live_v1_gdrive.yaml --paths-config configs\paths_local.yaml --validate-config` | `D:\Envs\yolo6d\python.exe scripts\run_live_pose.py --config configs\fzmotion_fixed_camera_live_v1_gdrive.yaml --paths-config configs\paths_local.yaml` |
| Fixed Kalman Filter | `scripts/smoke_replay_pipeline.py` | `configs/kalman_fixed.yaml` | Raw PnP pose | Raw and filtered pose | No | No | `D:\Envs\yolo6d\python.exe scripts\smoke_replay_pipeline.py --config configs\local_smoke_replay.yaml --kalman-config configs\kalman_fixed.yaml --validate-config` | `D:\Envs\yolo6d\python.exe scripts\smoke_replay_pipeline.py --config configs\local_smoke_replay.yaml --max-frames 3 --kalman-config configs\kalman_fixed.yaml` |
| Evaluation metrics | `src/yolo6d_car/evaluation/` | Future eval config | Predictions and mocap GT | Metrics/report | No | Yes later | Placeholder only | Future `scripts/evaluate_pose_results.py` |
| Data sync | `scripts/sync_capture_to_host.py` | CLI args | Laptop capture folder | Host `captures\<date>\<experiment>` | No | Yes for real sync | `D:\Envs\yolo6d\python.exe scripts\sync_capture_to_host.py --local-root data\examples\sync_test --host-root data\examples\sync_test_host --experiment demo --validate-config` | `D:\Envs\yolo6d\python.exe scripts\sync_capture_to_host.py --local-root D:\CaptureData\session --host-root G:\YOLO6D_Car_Data\captures --experiment session --verify` |

## Coverage Status

- Implemented skeleton: path management, Hik calibration, D455 capture, FzMotion CSV reading, auto labels, dataset build, training wrapper, replay, live realtime, fixed Kalman, data sync.
- Placeholder modules: reliability-aware Kalman, full evaluation reports.
- Real data still needed: captures, mocap CSVs, trained weights, final calibration sessions.
## Code Reading Notes

这份 checklist 适合作为总目录。读代码时建议把每一阶段对应到一个脚本入口：

- Path management: `src/yolo6d_car/path_utils.py`
- Replay smoke: `scripts/smoke_replay_pipeline.py`
- Capture: `scripts/capture_object_samples.py`
- Calibration: `scripts/calibrate_hik_camera.py`
- Labeling: `scripts/generate_mocap_labels.py`
- Dataset: `scripts/prepare_yolo_pose_dataset.py`, `scripts/manage_datasets.py`
- Tracking: `src/yolo6d_car/tracking/`
- Evaluation: `scripts/evaluate_pose_results.py`

如果某个阶段需要真实硬件，先看它是否支持 `--validate-config` 或 `--dry-run`。

