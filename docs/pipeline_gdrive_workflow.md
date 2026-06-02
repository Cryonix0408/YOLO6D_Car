# YOLO6D_Car G-Drive Pipeline Workflow

This guide describes the current workstation layout where code stays on `D:` and large data stays on `G:`.

Project root:

```powershell
D:\Research\YOLO6D_Car
```

Python:

```powershell
D:\Envs\yolo6d\python.exe
```

Data root:

```powershell
G:\YOLO6D_Car_Data
```

Path config:

```powershell
configs\paths_local.yaml
```

Always run commands from the project root unless a command says otherwise:

```powershell
cd D:\Research\YOLO6D_Car
```

## 1. Directory Convention

Keep source code, configs, small examples, and small model definition JSON files in the Git repo on `D:`.

```text
D:\Research\YOLO6D_Car
├── configs
├── data\examples
├── docs
├── models
├── scripts
└── src\yolo6d_car
```

Keep large data, captures, generated labels, datasets, training runs, weights, results, and logs on `G:`.

```text
G:\YOLO6D_Car_Data
├── captures
├── FZmotion_Data
├── outputs
│   ├── object_capture
│   ├── auto_labels
│   ├── datasets
│   └── train_runs
├── models
├── results
└── logs
```

Relative large-data paths are resolved through `configs\paths_local.yaml`:

- `FZmotion_Data\xxx.csv` -> `G:\YOLO6D_Car_Data\FZmotion_Data\xxx.csv`
- `outputs\auto_labels\run1` -> `G:\YOLO6D_Car_Data\outputs\auto_labels\run1`
- `outputs\datasets\run1` -> `G:\YOLO6D_Car_Data\outputs\datasets\run1`
- `outputs\train_runs\exp1` -> `G:\YOLO6D_Car_Data\outputs\train_runs\exp1`
- `models\best.pt` -> `G:\YOLO6D_Car_Data\models\best.pt`

Small repo files such as `models\car_custom_keypoints_12_migrated_200xx_exact.json` should stay on `D:`.

Some older historical docs may still contain legacy paths such as `D:\YOLO6D_Car` or repo-local `outputs\...`. Treat those as historical examples unless a current G-drive command is shown here.

## 2. Capture Workflow

Use the RealSense D455 capture scripts with a G-drive config and the path config.

Object/car capture:

```powershell
D:\Envs\yolo6d\python.exe scripts\capture_object_samples.py --config configs\object_capture_gdrive.yaml --paths-config configs\paths_local.yaml
```

Board capture:

```powershell
D:\Envs\yolo6d\python.exe scripts\capture_board_samples.py --config configs\board_capture_gdrive.yaml --paths-config configs\paths_local.yaml
```

Expected default output folder:

```text
G:\YOLO6D_Car_Data\outputs\object_capture\<timestamp>
G:\YOLO6D_Car_Data\outputs\board_capture\<timestamp>
```

For a named session, pass an explicit G-drive output directory:

```powershell
D:\Envs\yolo6d\python.exe scripts\capture_object_samples.py --config configs\object_capture_gdrive.yaml --paths-config configs\paths_local.yaml --output-dir G:\YOLO6D_Car_Data\outputs\object_capture\uav_4m_reshoot_d40_bgA_lightOn
```

Each capture session should contain enough metadata for later labeling:

- `images\` with captured RGB frames.
- `samples.csv` with image timestamps.
- `intrinsics.json` with RealSense camera intrinsics.
- `session_info.json` with capture/config context.
- Optional `depth\` if depth was saved.

## 3. Sync Workflow

Use `scripts\sync_capture_to_host.py` when the capture machine and host machine are separate.

Example laptop local capture path:

```text
D:\CaptureData\uav_4m_reshoot_d40_bgA_lightOn
```

Example host mapped drive:

```text
Z:\YOLO6D_Car_Data\captures
```

Dry run first:

```powershell
D:\Envs\yolo6d\python.exe scripts\sync_capture_to_host.py --local-root D:\CaptureData\uav_4m_reshoot_d40_bgA_lightOn --host-root Z:\YOLO6D_Car_Data\captures --experiment uav_4m_reshoot_d40_bgA_lightOn --date 2026-05-30 --dry-run
```

Actual sync:

```powershell
D:\Envs\yolo6d\python.exe scripts\sync_capture_to_host.py --local-root D:\CaptureData\uav_4m_reshoot_d40_bgA_lightOn --host-root Z:\YOLO6D_Car_Data\captures --experiment uav_4m_reshoot_d40_bgA_lightOn --date 2026-05-30
```

Expected final host path if `Z:` maps to the host data drive:

```text
G:\YOLO6D_Car_Data\captures\2026-05-30\uav_4m_reshoot_d40_bgA_lightOn
```

The sync script copies only new files, does not overwrite existing files, preserves the directory structure under `--local-root`, and writes:

```text
sync_log.txt
```

## 4. Automatic Mocap Labeling Workflow

Inputs:

- Captured image session, usually under `G:\YOLO6D_Car_Data\outputs\object_capture\<session>`.
- FzMotion CSV under `G:\YOLO6D_Car_Data\FZmotion_Data`.
- A config with camera rigid body, object rigid body, camera-to-optical transform, and object model settings.

Single-session labeling:

```powershell
D:\Envs\yolo6d\python.exe scripts\generate_mocap_labels.py --config configs\fzmotion_fixed_camera_current_rigids_gdrive.yaml --paths-config configs\paths_local.yaml --samples-dir outputs\object_capture\uav_4m_reshoot_d40_bgA_lightOn --csv-path FZmotion_Data\uav_4m_reshoot_d40_bgA_lightOn.csv --output-dir outputs\auto_labels\uav_4m_reshoot_d40_bgA_lightOn --save-overlays
```

Resolved output:

```text
G:\YOLO6D_Car_Data\outputs\auto_labels\uav_4m_reshoot_d40_bgA_lightOn
```

Batch labeling for the 20-session manifest:

```powershell
D:\Envs\yolo6d\python.exe scripts\batch_generate_mocap_labels.py --manifest configs\uav_4m_20_sessions_gdrive.yaml --paths-config configs\paths_local.yaml
```

Expected batch output root:

```text
G:\YOLO6D_Car_Data\outputs\auto_labels\uav_4m_20_sessions_batch
```

## 5. YOLO Pose Dataset Preparation

Prepare an Ultralytics Pose dataset from one or more auto-label directories.

Single auto-label directory:

```powershell
D:\Envs\yolo6d\python.exe scripts\prepare_yolo_pose_dataset.py --paths-config configs\paths_local.yaml --auto-label-dir outputs\auto_labels\uav_4m_reshoot_d40_bgA_lightOn --out-dir outputs\datasets\uav_4m_reshoot_d40_bgA_lightOn_pose --val-ratio 0.1 --seed 42 --class-name car_model --overwrite
```

Multiple sessions:

```powershell
D:\Envs\yolo6d\python.exe scripts\prepare_yolo_pose_dataset.py --paths-config configs\paths_local.yaml --auto-label-dir outputs\auto_labels\uav_4m_20_sessions_batch\d40_bgA_lightOn --auto-label-dir outputs\auto_labels\uav_4m_20_sessions_batch\d35_bgA_lightOn --out-dir outputs\datasets\uav_4m_20_sessions_pose --val-ratio 0.1 --seed 42 --class-name car_model --overwrite
```

Expected dataset folder:

```text
G:\YOLO6D_Car_Data\outputs\datasets\uav_4m_20_sessions_pose
```

Expected files:

```text
dataset.yaml
images\train
images\val
labels\train
labels\val
split_summary.json
```

The script creates a train/val split using `--val-ratio`. There is no separate test split unless you create one manually or add a future script option.

## 6. Training Workflow

Train an Ultralytics YOLO Pose model with outputs on G drive.

```powershell
D:\Envs\yolo6d\python.exe scripts\train_ultralytics_pose.py --paths-config configs\paths_local.yaml --dataset outputs\datasets\uav_4m_20_sessions_pose\dataset.yaml --model yolo11n-pose.pt --epochs 150 --imgsz 640 --batch 16 --device 0 --workers 4 --project outputs\train_runs --name uav_4m_20sessions_pose_v1
```

Expected training run folder:

```text
G:\YOLO6D_Car_Data\outputs\train_runs\uav_4m_20sessions_pose_v1
```

Expected best weight:

```text
G:\YOLO6D_Car_Data\outputs\train_runs\uav_4m_20sessions_pose_v1\weights\best.pt
```

Recommended export/copy convention for reusable weights:

```powershell
Copy-Item -LiteralPath G:\YOLO6D_Car_Data\outputs\train_runs\uav_4m_20sessions_pose_v1\weights\best.pt -Destination G:\YOLO6D_Car_Data\models\uav_4m_20sessions_pose_v1_best.pt -Force
```

Then live configs can use either:

```yaml
model_path: outputs/train_runs/uav_4m_20sessions_pose_v1/weights/best.pt
```

or:

```yaml
model_path: models/uav_4m_20sessions_pose_v1_best.pt
```

## 7. Replay Smoke Test

Baseline local smoke test:

```powershell
D:\Envs\yolo6d\python.exe scripts\smoke_replay_pipeline.py --config configs\local_smoke_replay.yaml --max-frames 3
```

G-drive smoke test:

```powershell
D:\Envs\yolo6d\python.exe scripts\smoke_replay_pipeline.py --config configs\local_smoke_replay_gdrive.yaml --paths-config configs\paths_local.yaml --max-frames 3
```

These should pass before and after path/config changes.

## 8. Live Inference Workflow

Default G-drive live config:

```powershell
D:\Envs\yolo6d\python.exe scripts\run_live_pose.py --config configs\fzmotion_fixed_camera_live_v1_gdrive.yaml --paths-config configs\paths_local.yaml
```

Fast-moving object live config:

```powershell
D:\Envs\yolo6d\python.exe scripts\run_live_pose.py --config configs\fzmotion_fast_moving_live_gdrive.yaml --paths-config configs\paths_local.yaml
```

Override model path at launch:

```powershell
D:\Envs\yolo6d\python.exe scripts\run_live_pose.py --config configs\fzmotion_fixed_camera_live_v1_gdrive.yaml --paths-config configs\paths_local.yaml --model models\uav_4m_20sessions_pose_v1_best.pt
```

Run headless and save CSV to G-drive logs/results:

```powershell
D:\Envs\yolo6d\python.exe scripts\run_live_pose.py --config configs\fzmotion_fixed_camera_live_v1_gdrive.yaml --paths-config configs\paths_local.yaml --model models\uav_4m_20sessions_pose_v1_best.pt --headless --save-csv results\live_pose_2026-05-30.csv
```

Enable mocap comparison during live inference:

```powershell
D:\Envs\yolo6d\python.exe scripts\run_live_pose.py --config configs\fzmotion_fixed_camera_live_v1_gdrive.yaml --paths-config configs\paths_local.yaml --model models\uav_4m_20sessions_pose_v1_best.pt --enable-mocap --csv-path FZmotion_Data\uav_4m_reshoot_d40_bgA_lightOn.csv
```

Expected model paths:

```text
G:\YOLO6D_Car_Data\outputs\train_runs\...\weights\best.pt
G:\YOLO6D_Car_Data\models\...\best.pt
```

Expected CSV/result paths:

```text
G:\YOLO6D_Car_Data\results
G:\YOLO6D_Car_Data\logs
G:\YOLO6D_Car_Data\outputs
```

Current runtime writes CSV logs. If you need video recording for live inference, add it explicitly in a future runtime change or record externally.

## 9. Troubleshooting

Missing `best.pt`:

```powershell
Test-Path G:\YOLO6D_Car_Data\outputs\train_runs\uav_4m_20sessions_pose_v1\weights\best.pt
Test-Path G:\YOLO6D_Car_Data\models\uav_4m_20sessions_pose_v1_best.pt
```

If both return `False`, train the model or copy the correct weight into `G:\YOLO6D_Car_Data\models`.

Missing FzMotion CSV:

```powershell
Test-Path G:\YOLO6D_Car_Data\FZmotion_Data\uav_4m_reshoot_d40_bgA_lightOn.csv
```

If it returns `False`, copy or sync the CSV to `G:\YOLO6D_Car_Data\FZmotion_Data`.

CUDA not available:

```powershell
D:\Envs\yolo6d\python.exe -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no cuda')"
```

If CUDA is `False`, check the NVIDIA driver, PyTorch CUDA build, and whether PyCharm/PowerShell is using `D:\Envs\yolo6d\python.exe`.

Paths still pointing to old `D:\YOLO6D_Car`:

```powershell
rg -n "D:\\YOLO6D_Car|D:\\Research\\YOLO6D_Car\\outputs|D:\\Research\\YOLO6D_Car\\FZmotion_Data" configs scripts src docs
```

Runtime configs should use `_gdrive.yaml` variants plus:

```powershell
--paths-config configs\paths_local.yaml
```

Mapped drive `Z:` not connected:

```powershell
Get-PSDrive Z
Test-Path Z:\
```

If `Z:` is missing, reconnect the network drive in Windows or use the actual UNC path if available.

Permission denied on G drive:

```powershell
Test-Path G:\YOLO6D_Car_Data
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data\logs\write_test
Remove-Item -LiteralPath G:\YOLO6D_Car_Data\logs\write_test
```

If directory creation fails, check Windows permissions, antivirus protection, drive mount state, or whether another process locked the folder.

Path parsing errors:

```powershell
D:\Envs\yolo6d\python.exe -c "from pathlib import Path; from yolo6d_car.path_utils import load_local_paths, resolve_path; lp=load_local_paths('configs/paths_local.yaml'); print(resolve_path('outputs/train_runs/test/weights/best.pt', project_root=Path.cwd(), local_paths=lp))"
```

Expected output should start with:

```text
G:\YOLO6D_Car_Data\outputs
```

## 10. Git Rules

Safe to commit:

- Source code under `src\`.
- Scripts under `scripts\`.
- Config files under `configs\`.
- Documentation under `docs\`.
- Small examples under `data\examples`.
- Small model definition JSON files under `models\`.
- `requirements.txt`, `.gitignore`, and README updates.

Never commit:

- `outputs\`
- `FZmotion_Data\`
- `captures\`
- `results\`
- `logs\`
- `data\real\`
- `data\synthetic\`
- Model weights or exports: `*.pt`, `*.pth`, `*.onnx`, `*.engine`
- Videos or RealSense bags: `*.mp4`, `*.avi`, `*.bag`
- Large arrays: `*.npy`, `*.npz`

Before committing, check for accidental large files:

```powershell
rg -n "G:\\YOLO6D_Car_Data|D:\\YOLO6D_Car|outputs\\train_runs|best\.pt" .
```

That command may show valid docs/config references. Do not commit actual large data or model weight files.

