# YOLO6D_Car 项目说明

## 本科生入门 / 项目阅读指南

第一次接触本项目，请先阅读以下三份文档：

- [本科生入门指南](docs/UNDERGRADUATE_GUIDE.md)：项目简介、Pipeline 说明、代码阅读顺序、可承担任务
- [环境准备与快速上手](docs/GETTING_STARTED.md)：环境安装、无设备使用模式、本地路径说明
- [正式版本与 Artifact 指南](docs/ARTIFACT_AND_VERSION_GUIDE.md)：各标定文件状态、Epoch 限制、坐标系约定

---

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

以下 `outputs/` 数据集和权重属于本机外部数据，不随 Git 仓库提供；如需使用请联系项目负责人。

- 当前推荐训练数据集：
  [uav_4m_20sessions_pose_20260413_v1_clean](./outputs/datasets/uav_4m_20sessions_pose_20260413_v1_clean)
- 当前推荐训练权重：
  [best.pt](./outputs/train_runs/uav_4m_20sessions_pose_v1/weights/best.pt)
- 当前正式标签配置：
  [fzmotion_hikvision_6mm_current_rigid1_20261007_003_labels.yaml](./configs/fzmotion_hikvision_6mm_current_rigid1_20261007_003_labels.yaml)
  使用 1007 Camera External、已验证的 Camera Bridge、正式 Rigid0 Registration 和当前 Car Model。
  2026-10-18 新版 Rigid0 不可直接复用旧 registration，须重新验证。
- 历史离线 / 标注配置（不作为当前正式标签入口）：
  [fzmotion_fixed_camera_current_rigids.yaml](./configs/fzmotion_fixed_camera_current_rigids.yaml)
- 当前实时推理配置模板：
  [fzmotion_fixed_camera_live_v1.yaml](./configs/fzmotion_fixed_camera_live_v1.yaml)

## 当前推荐入口

- 文档总入口：[docs/index.md](./docs/index.md)
- 常用命令：[docs/setup/common_commands.md](./docs/setup/common_commands.md)
- 笔记本采集流程：[docs/capture/laptop_lab_capture_workflow.md](./docs/capture/laptop_lab_capture_workflow.md)
- 相机架构：[docs/architecture/camera_architecture_zh.md](./docs/architecture/camera_architecture_zh.md)
- 标定流程：[docs/calibration/calibration_guide.md](./docs/calibration/calibration_guide.md)
- 训练流程：[docs/training/training_guide.md](./docs/training/training_guide.md)
- 评估流程：[docs/evaluation/mocap_gt_evaluation.md](./docs/evaluation/mocap_gt_evaluation.md)

## 文档导航

- 相机统一架构与本机实际路径：
  [docs/architecture/camera_architecture_zh.md](./docs/architecture/camera_architecture_zh.md)
- 相机配置迁移说明：
  [docs/cameras/camera_config_migration_zh.md](./docs/cameras/camera_config_migration_zh.md)
- 总体架构与流程：
  [docs/architecture/project_guide.md](./docs/architecture/project_guide.md)
- 接手清单：
  [docs/archive/handover_checklist.md](./docs/archive/handover_checklist.md)
- 环境部署与常见问题：
  [docs/setup/setup_and_faq.md](./docs/setup/setup_and_faq.md)
- 标定总说明：
  [docs/calibration/calibration_guide.md](./docs/calibration/calibration_guide.md)
- 相机刚体外参标定：
  [docs/calibration/camera_rigid_calibration.md](./docs/calibration/camera_rigid_calibration.md)
- 固定相机世界位姿说明：
  [docs/calibration/fixed_camera_calibration.md](./docs/calibration/fixed_camera_calibration.md)
- 自定义小车模型说明：
  [docs/labeling/custom_car_model.md](./docs/labeling/custom_car_model.md)
- Mocap 自动打标签：
  [docs/labeling/mocap_label_generation.md](./docs/labeling/mocap_label_generation.md)
- 训练说明：
  [docs/training/training_guide.md](./docs/training/training_guide.md)
- 实时推理说明：
  [docs/tracking/live_inference.md](./docs/tracking/live_inference.md)
- 高速运动跟踪与位姿估计：
  [docs/tracking/fast_moving_tracking.md](./docs/tracking/fast_moving_tracking.md)

## 相机架构说明

当前项目保留原有 D455 与 Hikrobot 底层实现，并新增统一相机适配层：

- `src/yolo6d_car/camera/base_camera.py`：统一 `BaseCamera` 与 `CameraFrame`
- `src/yolo6d_car/camera/factory.py`：根据配置创建 D455、Hikrobot 或 Webcam
- `src/yolo6d_car/camera/hikvision_stream.py`：海康 MVS 后端适配器
- `src/yolo6d_car/camera/webcam.py`：普通 USB 摄像头适配器

Hikrobot 6mm/8mm 配置中的内参路径推荐写成
`outputs/calibration/<lens>/camera_intrinsics_<lens>.yaml`。运行采集或
`--validate-config` 时，该路径会根据传入的 `configs/paths_local.yaml` 或
`configs/paths/paths_laptop.yaml` 分别解析到主机 G 盘或采集笔记本 `D:\CaptureData`；
历史绝对路径仍保持兼容。

采集笔记本当前实际项目路径为 `D:\YOLO6D_Car`，大数据根目录为
`D:\CaptureData`，应优先使用 `configs\paths\paths_laptop.yaml`。下方工作站路径仅用于
主机部署示例，不应直接复制到采集笔记本命令中。

## New workstation setup: code on D drive, data on G drive

本机推荐保持“代码和大数据分离”：

- 代码仓库：
  `D:\Research\YOLO6D_Car`
- Python 解释器：
  `D:\Envs\yolo6d\python.exe`
- 大数据根目录：
  `G:\YOLO6D_Car_Data`
- 本机路径配置：由 `configs/paths.example.yaml` 复制创建 `configs/paths_local.yaml`，并修改为本机路径。
  旧 `configs/paths/paths_local.yaml` 仅为历史工作站配置，不作为当前推荐入口。

推荐的大数据目录结构：

```text
G:\YOLO6D_Car_Data\FZmotion_Data
G:\YOLO6D_Car_Data\captures
G:\YOLO6D_Car_Data\outputs
G:\YOLO6D_Car_Data\outputs\object_capture
G:\YOLO6D_Car_Data\outputs\auto_labels
G:\YOLO6D_Car_Data\outputs\datasets
G:\YOLO6D_Car_Data\outputs\train_runs
G:\YOLO6D_Car_Data\models
G:\YOLO6D_Car_Data\results
G:\YOLO6D_Car_Data\logs
```

最小 smoke test：

```powershell
D:\Envs\yolo6d\python.exe .\scripts\smoke_replay_pipeline.py --config .\configs\replay\local_smoke_replay.yaml --max-frames 3
```

G 盘路径配置 smoke test：

```powershell
D:\Envs\yolo6d\python.exe .\scripts\smoke_replay_pipeline.py --config .\configs\local_smoke_replay_gdrive.yaml --paths-config .\configs\paths_local.yaml --max-frames 3
```

采集到 G 盘：

```powershell
D:\Envs\yolo6d\python.exe .\scripts\capture_object_samples.py `
  --config .\configs\object_capture.yaml `
  --paths-config .\configs\paths_local.yaml
```

使用 G 盘数据自动打标签：

```powershell
D:\Envs\yolo6d\python.exe .\scripts\generate_mocap_labels.py `
  --config .\configs\fzmotion_hikvision_6mm_current_rigid1_20261007_003_labels.yaml `
  --paths-config .\configs\paths_local.yaml `
  --samples-dir outputs/object_capture/<session_name> `
  --csv-path FZmotion_Data/<session_name>.csv `
  --output-dir outputs/auto_labels/<session_name> `
  --save-overlays
```

整理训练集到 G 盘：

```powershell
D:\Envs\yolo6d\python.exe .\scripts\prepare_yolo_pose_dataset.py `
  --paths-config .\configs\paths_local.yaml `
  --auto-label-dir outputs/auto_labels/<session_name> `
  --out-dir outputs/datasets/<dataset_name>
```

训练输出到 G 盘：

```powershell
D:\Envs\yolo6d\python.exe .\scripts\train_ultralytics_pose.py `
  --paths-config .\configs\paths_local.yaml `
  --dataset outputs/datasets/<dataset_name>/dataset.yaml `
  --model yolov8n-pose.pt `
  --project outputs/train_runs `
  --name <run_name>
```

同步采集端数据到主机 G 盘：

```powershell
D:\Envs\yolo6d\python.exe .\scripts\sync_capture_to_host.py `
  --local-root D:\CaptureData\<session_name> `
  --host-root G:\YOLO6D_Car_Data\captures `
  --experiment <session_name>
```

不要提交大数据或模型权重。`outputs/`、`FZmotion_Data/`、`captures/`、`results/`、`logs/`、`*.pt`、`*.pth`、`*.onnx`、`*.engine`、视频、RealSense `.bag`、NumPy 二进制文件都应留在 G 盘或本机数据目录中。

## 两台电脑数据同步

主机 / 工作站负责存储大数据：

- 主机数据目录：`G:\YOLO6D_Car_Data`
- 共享名建议：`YOLO6D_Car_Data`
- 采集笔记本映射：`Z:\ -> \\<HOST_IP>\YOLO6D_Car_Data`
- 采集笔记本本地采集目录：`D:\CaptureData\<session>`
- 同步目标：`Z:\captures\<date>\<session>`，对应主机 `G:\YOLO6D_Car_Data\captures\<date>\<session>`

详细设置步骤见：
[docs/setup/host_data_share_setup.md](./docs/setup/host_data_share_setup.md)

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
  --config .\configs\fzmotion_hikvision_6mm_current_rigid1_20261007_003_labels.yaml `
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

- 正式离线标签配置：
  [fzmotion_hikvision_6mm_current_rigid1_20261007_003_labels.yaml](./configs/fzmotion_hikvision_6mm_current_rigid1_20261007_003_labels.yaml)
- 历史离线配置：
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
  [car_custom_keypoints_12_current_rigid0_200xx.json](./models/car_custom_keypoints_12_current_rigid0_200xx.json)

### 数据与训练产物

- 最新 20-session 训练集：
  [uav_4m_20sessions_pose_20260413_v1_clean](./outputs/datasets/uav_4m_20sessions_pose_20260413_v1_clean)
- 最新训练结果目录：
  [uav_4m_20sessions_pose_v1](./outputs/train_runs/uav_4m_20sessions_pose_v1)
- 最新最佳权重：
  [best.pt](./outputs/train_runs/uav_4m_20sessions_pose_v1/weights/best.pt)

## 新同学接手建议

1. 先看 [docs/archive/handover_checklist.md](./docs/archive/handover_checklist.md)。
2. 再看 [docs/architecture/project_guide.md](./docs/architecture/project_guide.md) 理清整体数据流。
3. 如果要补采样本，先看 [docs/labeling/mocap_label_generation.md](./docs/labeling/mocap_label_generation.md)。
4. 如果要重新训练，直接看 [docs/training/training_guide.md](./docs/training/training_guide.md)。
5. 如果要现场演示或联调实时效果，直接看 [docs/tracking/live_inference.md](./docs/tracking/live_inference.md)。

## 说明

- `outputs/` 目录包含大量实验中间结果和训练产物，体积较大，不建议手动清理当前仍在使用的目录。
- 配置中的很多路径是 Windows 绝对路径，接手时第一件事就是核对本机路径是否一致。
- 当前项目默认围绕 `Rigid1`（相机）和 `Rigid0`（小车）这套命名约定展开，如果重新建刚体，需要同步更新 YAML。
# YOLO6D_Car 当前快速入口

如果你是第一次读这个项目，建议先看：

- [docs/architecture/project_code_reading_guide.md](./docs/architecture/project_code_reading_guide.md)
- [docs/setup/glossary.md](./docs/setup/glossary.md)
- [docs/capture/full_pipeline_checklist.md](./docs/capture/full_pipeline_checklist.md)
- [docs/capture/lab_execution_plan.md](./docs/capture/lab_execution_plan.md)

当前新工作站约定：

- 代码仓库：`D:\Research\YOLO6D_Car`
- Python：`D:\Envs\yolo6d\python.exe`
- 大数据根目录：`G:\YOLO6D_Car_Data`
- 路径配置：从 `configs\paths.example.yaml` 创建的本机 `configs\paths_local.yaml`

重要原则：代码、配置、文档、小型示例留在 D 盘 Git 仓库；真实 captures、FzMotion CSV、auto labels、datasets、train runs、best.pt、results、logs 放到 G 盘，不要提交到 Git。

当前完成状态：离线工程骨架基本完成，smoke replay / fixed KF / reliability-aware KF / ablation 小样例已建立；真实实验数据仍缺失，包括 Hikrobot 6mm/8mm 标定、真实 captures、FzMotion CSV、auto labels、dataset、train runs、best.pt、gt_pose.csv。

回实验室后优先顺序：先跑 readiness 和 validate-config，再完成 Hikrobot 镜头标定，然后采集 static / slow lateral / fast lateral 三个最小真实 session；每个 session 先做 capture quality、mocap quality、自动标签和标签可视化，overlay 正常后再构建 dataset 和训练。

## 离线色彩校正实验

- 工具：`scripts/test_color_correction.py`
- 配置：`configs/color_correction/rgb_wall_reference.yaml`
- 文档：[docs/experiments/color_correction_zh.md](./docs/experiments/color_correction_zh.md)

该工具利用图像中的红、绿、蓝参考区域离线测试 Gamma、HSV-V、RGB channel gain 和 3x3 CCM。它当前只用于实验验证，不接入正式采集 pipeline，也不能替代补光灯。
