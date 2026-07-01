# 主机 G 盘完整流程

本文档说明主机上的推荐目录结构和完整处理流程。主机负责训练、整理标签、跑评估；大数据放在 G 盘，代码放在 D 盘。

## 基本路径

项目根目录：

```text
D:\Research\YOLO6D_Car
```

Python：

```text
D:\Envs\yolo6d\python.exe
```

数据根目录：

```text
G:\YOLO6D_Car_Data
```

路径配置：

```text
configs\paths_local.yaml
```

除非特别说明，主机上运行命令前先进入项目：

```powershell
cd D:\Research\YOLO6D_Car
```

## 目录约定

Git 仓库只保存代码、小配置、小示例和文档：

```text
D:\Research\YOLO6D_Car
├── configs
├── data\examples
├── docs
├── models
├── scripts
└── src\yolo6d_car
```

大体积数据放到：

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

使用 `configs\paths_local.yaml` 后，相对路径会自动解析到 G 盘。例如：

- `FZmotion_Data\xxx.csv` -> `G:\YOLO6D_Car_Data\FZmotion_Data\xxx.csv`
- `outputs\auto_labels\run1` -> `G:\YOLO6D_Car_Data\outputs\auto_labels\run1`
- `outputs\datasets\run1` -> `G:\YOLO6D_Car_Data\outputs\datasets\run1`
- `outputs\train_runs\exp1` -> `G:\YOLO6D_Car_Data\outputs\train_runs\exp1`
- `models\best.pt` -> `G:\YOLO6D_Car_Data\models\best.pt`

小模型定义 JSON，例如 `models\car_custom_keypoints_12_migrated_200xx_exact.json`，仍然保留在 Git 仓库里。

## 数据同步

采集笔记本的数据通常先放在：

```text
D:\CaptureData\<session>
```

笔记本通过 `Z:\captures` 同步到主机：

```powershell
python .\scripts\sync_capture_batch_to_host.py --local-root D:\CaptureData --host-root Z:\captures --plan-only
python .\scripts\sync_capture_batch_to_host.py --local-root D:\CaptureData --host-root Z:\captures --verify
```

主机最终看到：

```text
G:\YOLO6D_Car_Data\captures\<date>\<session>
```

## Mocap 自动打标签

单个 session：

```powershell
D:\Envs\yolo6d\python.exe scripts\generate_mocap_labels.py --config configs\fzmotion_fixed_camera_current_rigids_gdrive.yaml --paths-config configs\paths_local.yaml --samples-dir captures\<date>\<session> --csv-path FZmotion_Data\raw_csv\<session>.csv --output-dir outputs\auto_labels\<session> --save-overlays
```

批量 session：

```powershell
D:\Envs\yolo6d\python.exe scripts\batch_generate_mocap_labels.py --manifest configs\uav_4m_20_sessions_gdrive.yaml --paths-config configs\paths_local.yaml
```

输出目录：

```text
G:\YOLO6D_Car_Data\outputs\auto_labels
```

## 构建 YOLO Pose 数据集

```powershell
D:\Envs\yolo6d\python.exe scripts\prepare_yolo_pose_dataset.py --paths-config configs\paths_local.yaml --auto-label-dir outputs\auto_labels\<session_or_batch> --out-dir outputs\datasets\<dataset_name> --val-ratio 0.1 --seed 42 --class-name car_model --overwrite
```

输出：

```text
G:\YOLO6D_Car_Data\outputs\datasets\<dataset_name>
```

## 训练

```powershell
D:\Envs\yolo6d\python.exe scripts\train_ultralytics_pose.py --paths-config configs\paths_local.yaml --dataset outputs\datasets\<dataset_name>\dataset.yaml --model yolo11n-pose.pt --epochs 150 --imgsz 640 --batch 16 --device 0 --workers 4 --project outputs\train_runs --name <run_name>
```

训练结果：

```text
G:\YOLO6D_Car_Data\outputs\train_runs\<run_name>
```

最佳权重：

```text
G:\YOLO6D_Car_Data\outputs\train_runs\<run_name>\weights\best.pt
```

推荐把可复用模型复制到：

```powershell
Copy-Item -LiteralPath G:\YOLO6D_Car_Data\outputs\train_runs\<run_name>\weights\best.pt -Destination G:\YOLO6D_Car_Data\models\<model_name>_best.pt -Force
```

## 实时推理

D455 旧配置：

```powershell
D:\Envs\yolo6d\python.exe scripts\run_live_pose.py --config configs\fzmotion_fixed_camera_live_v1_gdrive.yaml --paths-config configs\paths_local.yaml --model models\<model_name>_best.pt
```

fast-moving 配置：

```powershell
D:\Envs\yolo6d\python.exe scripts\run_live_pose.py --config configs\fzmotion_fast_moving_live_gdrive.yaml --paths-config configs\paths_local.yaml --model models\<model_name>_best.pt
```

无窗口保存 CSV：

```powershell
D:\Envs\yolo6d\python.exe scripts\run_live_pose.py --config configs\fzmotion_fast_moving_live_gdrive.yaml --paths-config configs\paths_local.yaml --model models\<model_name>_best.pt --headless --save-csv results\live_pose_<date>.csv
```

## 常见检查

检查模型是否存在：

```powershell
Test-Path G:\YOLO6D_Car_Data\models\<model_name>_best.pt
```

检查 CSV 是否存在：

```powershell
Test-Path G:\YOLO6D_Car_Data\FZmotion_Data\raw_csv\<session>.csv
```

检查 CUDA：

```powershell
D:\Envs\yolo6d\python.exe -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no cuda')"
```

检查路径解析：

```powershell
D:\Envs\yolo6d\python.exe -c "from pathlib import Path; from yolo6d_car.path_utils import load_local_paths, resolve_path; lp=load_local_paths('configs/paths_local.yaml'); print(resolve_path('outputs/train_runs/test', project_root=Path.cwd(), local_paths=lp))"
```

输出应以 `G:\YOLO6D_Car_Data\outputs` 开头。

## Git 规则

可以提交：

- `src\`
- `scripts\`
- `configs\`
- `docs\`
- `data\examples`
- 小型 JSON 模型定义
- `requirements.txt`
- `.gitignore`

不要提交：

- `captures\`
- `FZmotion_Data\`
- `outputs\`
- `results\`
- `logs\`
- `*.pt`
- `*.pth`
- `*.onnx`
- `*.engine`
- `*.mp4`
- `*.avi`
- `*.bag`
- `*.npy`
- `*.npz`

