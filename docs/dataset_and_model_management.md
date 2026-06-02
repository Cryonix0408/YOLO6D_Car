# Dataset and Model Management

This layer standardizes YOLO Pose dataset versions and trained model weights
without training or generating large data by itself.

## Why Dataset Manifest

`configs\dataset_manifest_template.yaml` records one dataset version:

- dataset name/version/task,
- source session manifest,
- train/val/test dataset folders,
- Ultralytics `dataset.yaml`,
- keypoint shape and class names,
- split policy and notes.

It keeps dataset structure reproducible when data is generated later from mocap
auto labels.

## Why Model Registry

`configs\model_registry_template.yaml` records planned or trained model
versions:

- `model_id`,
- dataset version,
- backbone checkpoint,
- train run directory,
- archived `best.pt` and `last.pt`,
- image size, epochs, batch,
- status and notes.

Replay and realtime configs should reference the archived model path under
`G:\YOLO6D_Car_Data\models\<model_id>\best.pt`.

## Naming

Dataset version:

```text
car_pose_12pts_v1
car_pose_12pts_real_v2
car_pose_12pts_fast_v3
```

Model id:

```text
<dataset>_<backbone-or-stage>
```

Examples:

```text
car_pose_12pts_v1_yolov8n_pose
car_pose_12pts_real_v2_yolov8s_pose
car_pose_12pts_fast_v3_yolov8s_finetune
```

## Generate Ultralytics dataset.yaml

```powershell
D:\Envs\yolo6d\python.exe scripts\manage_datasets.py ^
  --manifest configs\dataset_manifest_template.yaml ^
  --paths-config configs\paths_local.yaml ^
  --action generate-data-yaml
```

This writes the manifest's `paths.data_yaml`. With `paths_local.yaml`, that
resolves under `G:\YOLO6D_Car_Data\outputs\datasets\...`.

## Validate and Summarize

```powershell
D:\Envs\yolo6d\python.exe scripts\manage_datasets.py --manifest configs\dataset_manifest_template.yaml --paths-config configs\paths_local.yaml --action validate
D:\Envs\yolo6d\python.exe scripts\manage_models.py --registry configs\model_registry_template.yaml --paths-config configs\paths_local.yaml --action validate
```

Use `check-files` when you want a missing-file report. Planned datasets/models
may report missing files before real data or training exists.

## Print Training Command

```powershell
D:\Envs\yolo6d\python.exe scripts\manage_models.py ^
  --registry configs\model_registry_template.yaml ^
  --paths-config configs\paths_local.yaml ^
  --action print-train-command ^
  --model-id car_pose_12pts_v1_yolov8n_pose
```

The command is printed only. It does not train.

## Train

After real labels and `dataset.yaml` exist, run the printed command. It uses:

```text
scripts\train_ultralytics_pose.py
```

Training outputs go under:

```text
G:\YOLO6D_Car_Data\outputs\train_runs\<model_id>
```

## Archive best.pt

After training, archive weights:

```powershell
D:\Envs\yolo6d\python.exe scripts\archive_train_run.py ^
  --model-id car_pose_12pts_v1_yolov8n_pose ^
  --train-run outputs\train_runs\car_pose_12pts_v1_yolov8n_pose ^
  --registry configs\model_registry_template.yaml ^
  --paths-config configs\paths_local.yaml ^
  --dry-run
```

Remove `--dry-run` after checking the planned copy operations. By default,
existing `best.pt` is not overwritten. Use `--overwrite` only when you intend to
replace an archived model.

The archive directory is:

```text
G:\YOLO6D_Car_Data\models\car_pose_12pts_v1_yolov8n_pose
```

It contains:

- `best.pt`
- `last.pt`
- `args.yaml`
- `results.csv`
- `model_metadata.json`

The registry file is not edited automatically. After verifying the archive,
manually update the model status to `trained`.

## Replay and Realtime Model Reference

Use archived model weights in replay/realtime configs:

```yaml
yolo6d:
  model_path: "models/car_pose_12pts_v1_yolov8n_pose/best.pt"
```

With `--paths-config configs\paths_local.yaml`, this resolves to the G-drive
models root.

## Git Rules

Do not commit:

- `outputs/`
- `captures/`
- `results/`
- `logs/`
- `*.pt`
- `*.pth`
- `*.onnx`
- `*.engine`
- large videos, images, or arrays

It is fine to commit manifest templates, scripts, docs, and small examples.

## Future Training Stages

Record each stage as a separate `model_id`:

- synthetic pretrain,
- real-data fine-tune,
- fast-motion fine-tune,
- low-light or occlusion fine-tune,
- final paper model.

Keep the dataset version and source notes explicit so replay and ablation can
always identify which weights were used.
## Code Reading Notes

- Dataset manifest 管“训练数据集版本”，核心代码在 `src/yolo6d_car/dataset_manifest.py`。
- Model registry 管“模型和权重版本”，核心代码在 `src/yolo6d_car/model_registry.py`。
- `scripts/archive_train_run.py` 只归档训练输出，不自动修改 registry。

推荐顺序：

1. session labels 可视化正常。
2. 生成 dataset.yaml。
3. 打印训练命令。
4. 训练完成后 archive best.pt。
5. 手动更新 model registry 状态。
