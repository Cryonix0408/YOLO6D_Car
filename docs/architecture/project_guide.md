# 项目总说明

## 1. 项目目标

本项目的目标是构建一套适用于小车目标的 6DoF 位姿估计与数据闭环系统，覆盖以下环节：

1. 图像采集
2. 动捕真值读取
3. 相机外参标定
4. 小车关键点模型定义
5. 自动标签生成
6. 关键点模型训练
7. 实时推理与可视化

最终产出不是单独某一个脚本，而是一整套可复用流程。

## 2. 系统组成

### 采集侧

- `Intel RealSense D455`
- `scripts/capture_board_samples.py`
- `scripts/capture_object_samples.py`

### 动捕侧

- `FzMotion` 导出 CSV
- `src/yolo6d_car/mocap/csv_provider.py`

### 标定侧

- `scripts/solve_camera_rigid_to_optical.py`
- `scripts/compute_static_camera_pose.py`
- `scripts/refine_camera_rigid_to_optical_from_sessions.py`

### 模型与标签侧

- `models/car_custom_keypoints_12_migrated_200xx_exact.json`
- `scripts/build_custom_model_from_csv.py`
- `scripts/generate_mocap_labels.py`
- `scripts/batch_generate_mocap_labels.py`

### 训练与推理侧

- `scripts/prepare_yolo_pose_dataset.py`
- `scripts/train_ultralytics_pose.py`
- `scripts/run_pipeline.py`
- `src/yolo6d_car/pose/`

## 3. 核心数据流

```text
D455 图像
    ↓
object_capture / board_capture
    ↓
samples.csv + intrinsics.json + PNG 图像
    ↓
FzMotion CSV + 外参配置
    ↓
generate_mocap_labels.py
    ↓
auto_labels/<session>
    ↓
prepare_yolo_pose_dataset.py
    ↓
Ultralytics Pose 数据集
    ↓
train_ultralytics_pose.py
    ↓
best.pt
    ↓
run_pipeline.py + PnP
    ↓
实时 6DoF 位姿
```

## 4. 坐标系关系

项目里最重要的几个坐标系：

- `mocap_world`：动捕世界坐标系
- `Rigid1`：相机刚体坐标系
- `camera_optical`：相机光学坐标系
- `Rigid0`：小车刚体坐标系
- `car_model`：小车模型坐标系

离线标注时的关键关系是：

```text
T_camera_optical_car_model
= inv(T_world_camera_optical)
  * T_world_rigid0
  * T_rigid0_car_model
```

如果相机不是直接给 `T_world_camera_optical`，而是给 `Rigid1`，那么会多一段：

```text
T_world_camera_optical
= T_world_rigid1 * T_rigid1_camera_optical
```

## 5. 当前推荐工作流

### 场景 1：重新采集并补标数据

1. 采集图像
2. 检查 `samples.csv`
3. 用对应 FzMotion CSV 打标签
4. 抽查 overlay 质量
5. 合并成训练集

### 场景 2：重新训练

1. 先确认最新数据集路径
2. 默认优先从上一版 `best.pt` 继续 fine-tune
3. 训练结束后使用 `best.pt`
4. 再更新实时配置的 `model_path`

### 场景 3：现场实时演示

1. 检查 D455 是否被占用
2. 检查 `fzmotion_fixed_camera_live_v1.yaml`
3. 确认 `model_path` 指向正确权重
4. 运行 `run_pipeline.py`

## 6. 当前推荐文件

- 离线标注配置：
  [fzmotion_fixed_camera_current_rigids.yaml](../configs/fzmotion_fixed_camera_current_rigids.yaml)
- 20-session 数据集：
  [uav_4m_20sessions_pose_20260413_v1_clean](../outputs/datasets/uav_4m_20sessions_pose_20260413_v1_clean)
- 当前最佳权重：
  [best.pt](../outputs/train_runs/uav_4m_20sessions_pose_v1/weights/best.pt)

## 7. 建议接手顺序

1. 先看 [handover_checklist.md](./handover_checklist.md)
2. 再看 [setup_and_faq.md](./setup_and_faq.md)
3. 然后根据任务需要进入：
   - 标定：看 [calibration_guide.md](./calibration_guide.md)
   - 打标签：看 [mocap_label_generation.md](./mocap_label_generation.md)
   - 训练：看 [training_guide.md](./training_guide.md)
   - 实时运行：看 [live_inference.md](./live_inference.md)

