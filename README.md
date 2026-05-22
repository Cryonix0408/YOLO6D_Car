# YOLO6D_Car 项目说明

本项目用于完成一套面向小车目标的 6DoF 位姿估计流程，核心链路包括：

- 使用 `Intel RealSense D455` 采集图像
- 使用 `FzMotion` / 动捕系统提供相机与小车刚体位姿
- 基于动捕真值自动生成 2D 关键点标签
- 使用 `Ultralytics YOLO Pose` 训练关键点模型
- 基于 `PnP` 从 2D 关键点恢复小车 6DoF 位姿
- 在实时模式下显示检测、姿态和调试信息

当前项目已经具备完整闭环，可以直接用于：

- 标定板采集与外参求解
- 小车样本采集
- Mocap 自动打标签
- 多 session 数据集整理
- YOLO Pose 训练
- D455 实时推理

## 当前推荐版本

- 当前推荐训练数据集：
  [uav_4m_20sessions_pose_20260413_v1_clean](./outputs/datasets/uav_4m_20sessions_pose_20260413_v1_clean)
- 当前推荐训练权重：
  [best.pt](./outputs/train_runs/uav_4m_20sessions_pose_v1/weights/best.pt)
- 当前离线 / 标注配置：
  [fzmotion_fixed_camera_current_rigids.yaml](./configs/fzmotion_fixed_camera_current_rigids.yaml)
- 当前实时推理配置模板：
  [fzmotion_fixed_camera_live_v1.yaml](./configs/fzmotion_fixed_camera_live_v1.yaml)

## 文档导航

- 总体架构与流程：
  [docs/project_guide.md](./docs/project_guide.md)
- 接手清单：
  [docs/handover_checklist.md](./docs/handover_checklist.md)
- 环境部署与常见问题：
  [docs/setup_and_faq.md](./docs/setup_and_faq.md)
- 标定总说明：
  [docs/calibration_guide.md](./docs/calibration_guide.md)
- 相机刚体外参标定：
  [docs/camera_rigid_calibration.md](./docs/camera_rigid_calibration.md)
- 固定相机世界位姿说明：
  [docs/fixed_camera_calibration.md](./docs/fixed_camera_calibration.md)
- 自定义小车模型说明：
  [docs/custom_car_model.md](./docs/custom_car_model.md)
- Mocap 自动打标签：
  [docs/mocap_label_generation.md](./docs/mocap_label_generation.md)
- 训练说明：
  [docs/training_guide.md](./docs/training_guide.md)
- 实时推理说明：
  [docs/live_inference.md](./docs/live_inference.md)
- 高速运动跟踪与位姿估计：
  [docs/fast_moving_tracking.md](./docs/fast_moving_tracking.md)

## 目录结构

```text
YOLO6D_Car/
├─ configs/                 # 项目 YAML 配置
├─ data/examples/           # 示例输入数据
├─ docs/                    # 中文说明文档
├─ models/                  # 小车关键点模型 JSON
├─ scripts/                 # 采集、标定、打标签、训练脚本
├─ src/yolo6d_car/          # 核心源码
├─ FZmotion_Data/           # 动捕 CSV
└─ outputs/                 # 采集结果、标签、数据集、训练输出
```

## 最短可跑通流程

### 0. 最小健康检查

```powershell
& C:\Users\25701\venvs\yolo6d\Scripts\python.exe .\scripts\smoke_replay_pipeline.py --max-frames 3
```

### 1. 采集小车图像

```powershell
python .\scripts\capture_object_samples.py --config .\configs\object_capture.yaml
```

### 2. 生成 Mocap 自动标签

```powershell
python .\scripts\generate_mocap_labels.py `
  --config .\configs\fzmotion_fixed_camera_current_rigids.yaml `
  --samples-dir .\outputs\object_capture\<session_name> `
  --csv-path D:\YOLO6D_Car\FZmotion_Data\<session_name>.csv `
  --output-dir .\outputs\auto_labels\<session_name> `
  --save-overlays
```

### 3. 合并为训练数据集

```powershell
python .\scripts\prepare_yolo_pose_dataset.py `
  --auto-label-dir .\outputs\auto_labels\<session_1> `
  --auto-label-dir .\outputs\auto_labels\<session_2> `
  --out-dir .\outputs\datasets\<dataset_name>
```

### 4. 训练 YOLO Pose

```powershell
python .\scripts\train_ultralytics_pose.py `
  --dataset .\outputs\datasets\uav_4m_20sessions_pose_20260413_v1_clean\dataset.yaml `
  --model .\outputs\train_runs\uav_4m_20sessions_pose_v1\weights\best.pt `
  --epochs 120 `
  --imgsz 640 `
  --batch 16 `
  --project .\outputs\train_runs `
  --name uav_4m_20sessions_pose_v1
```

### 5. 实时推理

```powershell
python .\scripts\run_pipeline.py --config .\configs\fzmotion_fixed_camera_live_v1.yaml
```

如果要切换到最新权重，请先修改 `configs/fzmotion_fixed_camera_live_v1.yaml` 中的 `model_path`。

## 当前关键文件

### 配置

- 离线打标签 / 回放：
  [fzmotion_fixed_camera_current_rigids.yaml](./configs/fzmotion_fixed_camera_current_rigids.yaml)
- 实时推理：
  [fzmotion_fixed_camera_live_v1.yaml](./configs/fzmotion_fixed_camera_live_v1.yaml)
- 高速运动实时推理：
  [fzmotion_fast_moving_live.yaml](./configs/fzmotion_fast_moving_live.yaml)
- 小车采集：
  [object_capture.yaml](./configs/object_capture.yaml)
- 标定板采集：
  [board_capture.yaml](./configs/board_capture.yaml)
- 20 个 session 批处理清单：
  [uav_4m_20_sessions.yaml](./configs/uav_4m_20_sessions.yaml)

### 模型

- 当前 12 点小车模型：
  [car_custom_keypoints_12_migrated_200xx_exact.json](./models/car_custom_keypoints_12_migrated_200xx_exact.json)

### 数据与训练产物

- 最新 20-session 训练集：
  [uav_4m_20sessions_pose_20260413_v1_clean](./outputs/datasets/uav_4m_20sessions_pose_20260413_v1_clean)
- 最新训练结果目录：
  [uav_4m_20sessions_pose_v1](./outputs/train_runs/uav_4m_20sessions_pose_v1)
- 最新最佳权重：
  [best.pt](./outputs/train_runs/uav_4m_20sessions_pose_v1/weights/best.pt)

## 新同学接手建议

1. 先看 [docs/handover_checklist.md](./docs/handover_checklist.md)。
2. 再看 [docs/project_guide.md](./docs/project_guide.md) 理清整体数据流。
3. 如果要补采样本，先看 [docs/mocap_label_generation.md](./docs/mocap_label_generation.md)。
4. 如果要重新训练，直接看 [docs/training_guide.md](./docs/training_guide.md)。
5. 如果要现场演示或联调实时效果，直接看 [docs/live_inference.md](./docs/live_inference.md)。

## 说明

- `outputs/` 目录包含大量实验中间结果和训练产物，体积较大，不建议手动清理当前仍在使用的目录。
- 配置中的很多路径是 Windows 绝对路径，接手时第一件事就是核对本机路径是否一致。
- 当前项目默认围绕 `Rigid1`（相机）和 `Rigid0`（小车）这套命名约定展开，如果重新建刚体，需要同步更新 YAML。


