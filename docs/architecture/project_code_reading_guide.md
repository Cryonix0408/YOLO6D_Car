# Project Code Reading Guide

这份文档给第一次阅读 YOLO6D_Car 的人使用。目标不是马上跑实验，而是先看懂每个模块在完整 pipeline 中的位置。

## 推荐阅读顺序

1. `README.md`
2. `docs/full_pipeline_checklist.md`
3. `configs/paths_local.yaml`
4. `src/yolo6d_car/path_utils.py`
5. `scripts/check_project_readiness.py`
6. `scripts/smoke_replay_pipeline.py`
7. `src/yolo6d_car/pipeline.py`
8. `src/yolo6d_car/tracking/`
9. `src/yolo6d_car/evaluation/`
10. `scripts/run_kalman_ablation.py`
11. `src/yolo6d_car/session_manifest.py`
12. `src/yolo6d_car/dataset_manifest.py`
13. `src/yolo6d_car/model_registry.py`
14. capture / calibration / labeling 相关脚本

## 完整流程图

```text
capture
-> mocap csv
-> generate labels
-> visualize labels
-> prepare dataset
-> train YOLO Pose
-> replay PnP
-> Kalman
-> evaluation
-> ablation
-> paper results
```

## 模块和文件

| 模块 | 关键文件 | 作用 |
|---|---|---|
| 路径管理 | `configs/paths_local.yaml`, `src/yolo6d_car/path_utils.py` | D 盘代码 / G 盘数据解析 |
| 配置加载 | `src/yolo6d_car/config.py` | YAML -> ProjectConfig |
| replay pipeline | `scripts/smoke_replay_pipeline.py`, `src/yolo6d_car/pipeline.py` | 读取 replay/keypoints，PnP，输出 pose |
| tracking | `src/yolo6d_car/tracking/pose_kalman_filter.py`, `reliability_estimator.py` | fixed KF 和 reliability-aware KF |
| evaluation | `scripts/evaluate_pose_results.py`, `src/yolo6d_car/evaluation/*` | jitter、smoothness、GT 误差 |
| ablation | `scripts/run_kalman_ablation.py` | raw/fixed/reliability 三方法对比 |
| session 管理 | `src/yolo6d_car/session_manifest.py`, `scripts/manage_sessions.py` | 管理每次采集 session |
| dataset 管理 | `src/yolo6d_car/dataset_manifest.py`, `scripts/manage_datasets.py` | 管理 YOLO Pose 数据集版本 |
| model 管理 | `src/yolo6d_car/model_registry.py`, `scripts/manage_models.py` | 管理模型权重和训练命令 |
| 自动采集 | `scripts/capture_object_samples.py` | 一个人采集小车样本 |
| 标定 | `scripts/calibrate_hik_camera.py`, `src/yolo6d_car/calibration/*` | 6mm/8mm 海康内参标定 |
| 自动标签 | `scripts/generate_mocap_labels.py` | Mocap GT -> 2D keypoint labels |
| 标签检查 | `scripts/visualize_auto_labels.py` | overlay 检查标签质量 |

## 可以离线读懂和测试的代码

- `path_utils.py`
- `config.py`
- `smoke_replay_pipeline.py`
- `pose_kalman_filter.py`
- `reliability_estimator.py`
- `evaluate_pose_results.py`
- `run_kalman_ablation.py`
- `session_manifest.py`
- `dataset_manifest.py`
- `model_registry.py`
- `manage_*` 脚本

这些模块不需要真实相机即可阅读或 smoke test。

## 必须回实验室才能验证的代码

- Hikrobot / D455 真实采集
- Hikrobot 6mm / 8mm 标定
- FzMotion 实时或真实 CSV 采集
- 自动标签在真实 mocap/capture 上的正确性
- realtime pose
- 真实 fast-moving ablation

## Placeholder 模块

- `src/yolo6d_car/tracking/pose_gating.py`
- `src/yolo6d_car/tracking/state_machine.py`
- `src/yolo6d_car/evaluation/compare_with_mocap.py`

这些文件主要预留结构，当前正式逻辑不依赖它们的复杂实现。

## 容易混淆的概念

- raw pose vs filtered pose：raw 是 PnP 直接输出，filtered 是 Kalman 输出。
- replay vs realtime：replay 用离线 JSON/CSV 跑流程；realtime 连接真实相机。
- session vs dataset vs model：session 是一次采集；dataset 是多个 session 组成的训练集；model 是训练结果。
- capture metadata vs session manifest：metadata 是采集现场记录；manifest 是项目级索引。
- camera intrinsics vs mocap extrinsics：内参描述相机成像；外参/刚体变换描述坐标系关系。
- FzMotion CSV vs gt_pose.csv：前者是原始动捕数据；后者是评估用的预处理 GT pose。
- fixed KF vs reliability-aware KF：fixed 使用固定 R；reliability-aware 根据观测质量动态缩放 R。

## 建议第一天只读这些文件

1. `configs/paths_local.yaml`
2. `scripts/smoke_replay_pipeline.py`
3. `src/yolo6d_car/pipeline.py`
4. `src/yolo6d_car/tracking/pose_kalman_filter.py`
5. `scripts/evaluate_pose_results.py`
6. `configs/session_manifest_template.yaml`
7. `scripts/process_single_session.py`
