# 数据集和模型管理

本文档说明如何把自动标签整理成 YOLO Pose 数据集，以及如何管理训练出来的模型。

## 数据集目录

数据集通常放在：

```text
G:\YOLO6D_Car_Data\outputs\datasets\<dataset_name>
```

典型结构：

```text
<dataset_name>
├── images
│   ├── train
│   └── val
├── labels
│   ├── train
│   └── val
├── dataset.yaml
└── split_summary.json
```

## 从自动标签生成数据集

```powershell
D:\Envs\yolo6d\python.exe scripts\prepare_yolo_pose_dataset.py ^
  --paths-config configs\paths_local.yaml ^
  --auto-label-dir outputs\auto_labels\<session_or_batch> ^
  --out-dir outputs\datasets\<dataset_name>
```

如果是多个 session，建议先把 auto labels 汇总好，再生成统一数据集。

## 训练

```powershell
D:\Envs\yolo6d\python.exe scripts\train_ultralytics_pose.py ^
  --paths-config configs\paths_local.yaml ^
  --dataset outputs\datasets\<dataset_name>\dataset.yaml ^
  --model yolo11n-pose.pt ^
  --device 0 ^
  --project outputs\train_runs ^
  --name <run_name>
```

训练结果通常在：

```text
G:\YOLO6D_Car_Data\outputs\train_runs\<run_name>
```

最重要的权重：

```text
weights\best.pt
```

## 模型归档

训练完成后，建议把可用模型复制或登记到：

```text
G:\YOLO6D_Car_Data\models
```

模型命名建议包含：

- 相机类型
- 镜头
- 数据集版本
- 是否 fast-moving
- 日期

例如：

```text
car_pose_hik_8mm_fastmoving_v1_yolo11n_pose
```

## 不要放进 Git 的内容

以下内容不要提交：

- `outputs\datasets`
- `outputs\train_runs`
- `models\*.pt`
- `*.pt`
- `*.onnx`
- `*.engine`

代码用 Git，同步和训练数据走共享盘。

## 检查点

训练前确认：

- `dataset.yaml` 中路径正确。
- 训练集和验证集都有图片和标签。
- 标签可视化没有明显错位。
- 关键点数量和模型定义一致。
- `kpt_shape` 和数据集标签一致。

训练后确认：

- `best.pt` 存在。
- `results.png` 曲线正常。
- 验证集指标不是异常虚高或异常为 0。
- 用几张真实图片做推理检查。

