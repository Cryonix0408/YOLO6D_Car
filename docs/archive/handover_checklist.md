# 项目接手清单

这份文档给第一次接手本项目的人使用。按照下面的顺序做，通常不会迷路。

## 1. 先确认的事情

- 工程根目录是否为 `D:\YOLO6D_Car`
- Python 环境是否可用
- replay smoke test 是否能通过：
  `C:\Users\25701\venvs\yolo6d\Scripts\python.exe .\scripts\smoke_replay_pipeline.py --max-frames 3`
- D455 是否可正常被 RealSense SDK 打开
- FzMotion CSV 路径是否和配置一致
- `outputs/` 里的最新训练权重是否存在

## 2. 先看哪些文件

### 先看文档

- [README.md](../README.md)
- [project_guide.md](./project_guide.md)
- [setup_and_faq.md](./setup_and_faq.md)

### 再看配置

- [fzmotion_fixed_camera_current_rigids.yaml](../configs/fzmotion_fixed_camera_current_rigids.yaml)
- [fzmotion_fixed_camera_live_v1.yaml](../configs/fzmotion_fixed_camera_live_v1.yaml)
- [uav_4m_20_sessions.yaml](../configs/uav_4m_20_sessions.yaml)

### 再看核心脚本

- [generate_mocap_labels.py](../scripts/generate_mocap_labels.py)
- [prepare_yolo_pose_dataset.py](../scripts/prepare_yolo_pose_dataset.py)
- [train_ultralytics_pose.py](../scripts/train_ultralytics_pose.py)
- [run_pipeline.py](../scripts/run_pipeline.py)

## 3. 现在正在用的资源

- 最新训练集：
  [uav_4m_20sessions_pose_20260413_v1_clean](../outputs/datasets/uav_4m_20sessions_pose_20260413_v1_clean)
- 最新训练结果：
  [uav_4m_20sessions_pose_v1](../outputs/train_runs/uav_4m_20sessions_pose_v1)
- 最新最佳权重：
  [best.pt](../outputs/train_runs/uav_4m_20sessions_pose_v1/weights/best.pt)
- 当前小车 12 点模型：
  [car_custom_keypoints_12_migrated_200xx_exact.json](../models/car_custom_keypoints_12_migrated_200xx_exact.json)

## 4. 如果你要做什么

### 如果你要补采图像

看 [mocap_label_generation.md](./mocap_label_generation.md) 里的采集与打标签流程。

### 如果你要重做标定

看 [calibration_guide.md](./calibration_guide.md) 和 [camera_rigid_calibration.md](./camera_rigid_calibration.md)。

### 如果你要重新训练

看 [training_guide.md](./training_guide.md)。

### 如果你要直接现场演示

看 [live_inference.md](./live_inference.md)。

## 5. 最容易踩坑的地方

- `samples.csv`、图像目录、FzMotion CSV 三者必须对应同一个 session。
- 如果重新建立了刚体，YAML 里的刚体名、外参和时间偏置都要重新确认。
- `PowerShell` 环境在某些机器上可能会被执行策略影响，直接复制命令没反应时先看 [setup_and_faq.md](./setup_and_faq.md)。
- 实时推理前一定要确认 `model_path` 指向正确的 `best.pt`。
- 重建同名数据集时要确认输出目录；脚本默认拒绝覆盖，确认无误后再加 `--overwrite`。

