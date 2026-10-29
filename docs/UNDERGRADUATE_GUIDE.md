# 本科生入门指南

> 适合第一次接触本项目的同学。阅读本文档不需要运行任何代码，先建立整体认知，再按顺序阅读代码。

---

## 1. 项目简介

### 研究方向

Fast-moving Object Tracking & 6DoF Pose Estimation（快速运动目标跟踪与六自由度位姿估计）

### 项目目标

```
RGB 图像
  → YOLO Pose（检测 + 12×2D 关键点）
  → PnP 求解
  → Raw 6DoF Pose
  → Kalman / Reliability-aware KF
  → Final Pose
```

### 关键概念

**什么是 6DoF？**
6DoF = 6 Degrees of Freedom（六个自由度）：空间中一个物体的完整姿态，包括三个平移（x、y、z）和三个旋转（roll、pitch、yaw）。本项目目标是从单目 RGB 图像实时估计小车相对于相机的完整 6DoF 位姿。

**为什么需要关键点？**
直接从图像估计 6DoF 很困难。本项目改用间接方法：先用 YOLO Pose 检测小车上的 12 个预定义 3D 关键点在图像中的 2D 投影位置，再用 PnP 算法从"3D 关键点 ↔ 2D 像素对"恢复完整位姿。

**YOLO Pose 负责什么？**
YOLO Pose 是一个深度学习检测模型，输出每帧图像中的：
- 目标检测框（BBox）
- 12 个关键点的 2D 像素坐标
- 每个关键点的置信度

**PnP 负责什么？**
PnP（Perspective-n-Point）是一个经典计算机视觉算法，输入：12 个已知的 3D 关键点位置（来自 Car Model）+ 对应的 2D 像素坐标（来自 YOLO）+ 相机内参，输出：`T_CameraOptical_CarModel`，即小车相对于相机的 6DoF 位姿。

**为什么使用 Kalman？**
PnP 是单帧求解，容易受关键点噪声、遮挡影响导致帧间跳变。Kalman Filter 利用运动模型对连续帧位姿进行平滑和预测，提高稳定性。项目还实现了 Reliability-aware KF，根据当前帧的置信度、重投影误差动态调整滤波器的信任程度。

**Mocap（动捕）在项目中的作用？**
FzMotion 动捕系统提供高精度的刚体（相机和小车）绝对位姿，用于：
1. 自动生成 YOLO Pose 训练标签（不需要人工标注）
2. 作为 Ground Truth 评估 PnP 输出的精度
3. 相机外参标定

---

## 2. 技术架构

### A. 数据采集（需实验室设备）

```
Hikrobot 6mm 工业相机  →  原始图像（1440×1080，60fps）
FzMotion Mocap 系统    →  刚体位姿 CSV（Rigid0=小车，Rigid1=相机）
```

涉及脚本：`scripts/capture_object_samples.py`、`scripts/collect_hikvision_sequence.py`

### B. 自动标注（核心环节，已实现并验证）

```
Mocap Pose（CSV）
  + Car Model 3D 关键点
  + Camera 外参 + Bridge
  → 坐标变换链
  → 投影到图像平面
  → 2D 关键点标签（YOLO Pose 格式）
```

正式脚本：`scripts/generate_mocap_labels.py`
正式配置：`configs/fzmotion_hikvision_6mm_current_rigid1_20261007_003_labels.yaml`

已完成：static0004 六帧格式验证（41 字段，PASS）。视觉语义质量（关键点逐点确认）尚未完整验收。

### C. 模型训练（需 GPU，已有权重）

```
图像 + YOLO Pose 标签  →  Ultralytics YOLO Pose 训练  →  best.pt
```

当前可用权重：`outputs/train_runs/uav_4m_20sessions_pose_v1/weights/best.pt`

脚本：`scripts/train_ultralytics_pose.py`

### D. 正式推理（已实现，待完整评估）

```
RGB 图像
  → UltralyticsLiveBackend（YOLO Pose 检测）
  → PnP（12×2D → 6DoF）
  → TemporalPoseFilter
  → PoseKalmanFilter（仅 json_replay 模式已接入，live 模式待完成）
  → 最终位姿输出
```

主要文件：`src/yolo6d_car/pipeline.py`

**已知问题：** `ultralytics_live` 后端目前不经过 Kalman 分支，仅 `json_replay` 后端走完整 KF 流程。

### E. 评估（框架已实现，GT 链路已修复）

```
PnP 预测位姿  vs  Mocap GT 位姿（Camera Optical 帧下的 T_CameraOptical_CarModel）
```

评估脚本：`scripts/evaluate_pose_results.py`

**已知状态：** Pipeline 的 Mocap GT 路径（`_world_camera_optical_pose`）在 2026-10-27 已修复 Camera Bridge 缺失问题。修复前的历史 CSV 日志的 `mocap_*` 列存在 4.347° 系统性偏差，需重跑才能更新。

---

## 3. 项目目录结构

```
D:\YOLO6D_Car\
├── src/yolo6d_car/          # 核心库代码
│   ├── pipeline.py          # 推理主流水线
│   ├── config.py            # 配置加载与强类型定义
│   ├── transforms.py        # SE(3) 坐标变换工具
│   ├── types.py             # PoseSE3、CameraIntrinsics 等类型定义
│   ├── object_model.py      # Car Model 3D 关键点加载
│   ├── visualization.py     # 叠加绘制工具
│   ├── mocap/               # FzMotion CSV 解析
│   ├── pose/                # PnP 求解、TemporalPoseFilter
│   ├── tracking/            # Kalman Filter、ReliabilityEstimator
│   ├── camera/              # Hikrobot 相机驱动
│   └── calibration/         # 标定采集辅助
├── scripts/                 # 命令行入口脚本（采集、标注、训练、评估等）
├── configs/                 # 所有配置文件
│   ├── calibration/         # 标定 artifact（正式 + 历史）
│   ├── capture/             # 采集配置
│   └── *.yaml               # 主流程配置
├── models/                  # Car Model JSON（3D 关键点定义）
├── docs/                    # 文档（本文件所在目录）
├── data/examples/           # 少量示例数据（已纳入 git）
├── tests/                   # 单元测试
├── tools/                   # 辅助工具脚本
├── outputs/                 # 训练权重、标签输出（已 .gitignore）
├── requirements.txt         # Python 依赖
└── README.md                # 项目入口
```

---

## 4. 关键代码阅读顺序

### 第 1 步：类型定义与坐标约定

**文件：** `src/yolo6d_car/types.py`；`docs/coordinate_frame_convention.md` 未随本共享版本提供，坐标约定可先参考本文与 Artifact 指南。
**功能：** 定义 `PoseSE3`（带 frame 标签的 SE(3) 位姿）、`CameraIntrinsics` 等基础类型
**重点函数：** `PoseSE3` 的字段含义
**前置知识：** Python dataclass、齐次坐标

---

### 第 2 步：SE(3) 坐标变换

**文件：** `src/yolo6d_car/transforms.py`
**功能：** 所有坐标变换工具（compose_poses、invert_pose、quaternion_to_matrix 等）
**重点函数：** `compose_poses`（注意 frame 校验逻辑）
**项目约定：** `p_A = T_A_B @ p_B`，即 `T_A_B` 表示 B→A 变换
**前置知识：** 旋转矩阵、四元数、齐次变换矩阵

---

### 第 3 步：配置加载

**文件：** `src/yolo6d_car/config.py`
**功能：** 把 YAML 配置解析成强类型 dataclass，包括 Camera Bridge 的 SHA256 验证
**重点函数：** `load_config`、`_load_camera_rigid_bridge`
**前置知识：** Python dataclass、YAML

---

### 第 4 步：Mocap 数据解析

**文件：** `src/yolo6d_car/mocap/csv_provider.py`
**功能：** 解析 FzMotion CSV，提供 `get_pose`（最近邻）和 `get_pose_window`（时间窗口）查询
**重点函数：** `get_pose`、`get_pose_window`
**前置知识：** 时间序列、二分查找

---

### 第 5 步：自动标注流程

**文件：** `scripts/generate_mocap_labels.py`
**功能：** 完整自动标注流程，包括时间戳对齐、robust-window 聚合、坐标变换链、投影、格式写出
**重点函数：** `_robust_static_pose`、`_compute_bbox_xyxy`、`_bbox_to_yolo_xywh`
**前置知识：** 第 1–4 步 + 相机投影模型

---

### 第 6 步：YOLO Pose 后端

**文件：** `src/yolo6d_car/pose/yolo6d_interface.py`
**功能：** `UltralyticsLiveBackend`（实时推理）和 `JSONReplayBackend`（离线回放）
**前置知识：** Ultralytics YOLO API 基础

---

### 第 7 步：PnP 求解

**文件：** `src/yolo6d_car/pose/pnp.py`
**功能：** 封装 OpenCV `solvePnPRansac`，输入 2D–3D 对应点，输出 `PoseSE3`
**前置知识：** PnP 原理、OpenCV solvePnP

---

### 第 8 步：推理主流水线

**文件：** `src/yolo6d_car/pipeline.py`
**功能：** 把取流、YOLO、PnP、KF、Mocap GT、可视化、日志串起来
**重点函数：** `PosePipeline.run`、`_compute_mocap_pose`、`_world_camera_optical_pose`
**注意：** Kalman 目前只在 `json_replay` 模式初始化

---

### 第 9 步：Kalman Filter

**文件：** `src/yolo6d_car/tracking/pose_kalman_filter.py`、`src/yolo6d_car/tracking/reliability_estimator.py`
**功能：** 6DoF Kalman 滤波、Reliability-aware 动态噪声调整
**前置知识：** Kalman Filter 原理

---

## 5. 学习前置知识

| 主题 | 说明 | 推荐资源 |
|---|---|---|
| Python / NumPy | 矩阵运算、数组索引 | NumPy 官方教程 |
| 线性代数 | 矩阵乘法、行列式、逆矩阵、特征值 | MIT 18.06 公开课 |
| 坐标系与 SE(3) | 旋转矩阵、四元数、齐次变换矩阵 | 《Robotics: Modelling, Planning and Control》第 2 章 |
| 相机模型 | 针孔相机、内参矩阵、畸变系数 | OpenCV Camera Calibration 文档 |
| 3D→2D 投影 | 世界坐标 → 相机坐标 → 图像坐标 | OpenCV projectPoints 文档 |
| PnP 算法 | 从 2D–3D 对应点求解位姿 | OpenCV solvePnP 文档、EPnP 论文 |
| YOLO Pose | 关键点检测基础 | Ultralytics Pose 文档 |
| Kalman Filter | 状态估计、预测-更新循环 | Probabilistic Robotics 第 3 章 |

---

## 6. 本科生能够承担的任务

### 入门任务（无需设备）

- 阅读 `types.py`、`transforms.py`，理解 `PoseSE3` 和坐标约定
- 读取 `models/car_custom_keypoints_12_current_rigid0_200xx.json`，画出 12 个关键点的 3D 位置分布图
- 读取 `data/examples/mocap_sample.csv`，理解 FzMotion CSV 格式
- 查看 `D:/CaptureData/outputs/auto_labels/car_static_0004_*/overlays/` 下的已有 overlay 图像

### 中级任务（需要部分数据，无需设备）

- 对 6 帧 static0004 数据，用 `scripts/visualize_auto_labels.py` 重新生成可视化
- 编写脚本读取已有正式标签，计算 12 个关键点的帧间稳定性
- 读取 `data/examples/gt_evaluation_test/` 下的示例数据，运行 `scripts/evaluate_pose_results.py` 了解评估流程

### 高级任务（需要实验室设备或完整数据集）

- 扩大 formal smoke 规模，增加多 yaw、多距离数据
- 对比 `json_replay` 模式下 Kalman ON/OFF 的位姿误差
- 协助实现 `ultralytics_live` 后端的 Kalman 接入
- 实测 Rigid0 marker 平面到轮底的物理距离，确认 BBox 底面几何修正量

> **注意：** 以下任务目前不适合本科生独立承担：
> - 修改 Camera Bridge、Rigid0 Registration 或 Car Model
> - 使用 2026-10-18 新 Rigid0 数据替换现有 production 配置
> - 重新运行完整标定流程

---

*最后更新：2026-10-29*
