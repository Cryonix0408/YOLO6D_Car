# YOLO6D_Car 文档总入口

这个页面是当前项目文档的入口索引，用来快速找到采集、标定、自动标签、训练、实时推理、Kalman 跟踪、评估和数据同步相关说明。当前阶段以“保持旧命令兼容、先理清入口”为目标，暂时不移动脚本、配置和代码。

## 项目总览

- [README.md](../README.md)：项目主入口，包含当前推荐版本、总体链路和常用文档入口。
- [docs/project_guide.md](project_guide.md)：项目整体流程说明，适合第一次接手时从头读。
- [docs/common_commands.md](common_commands.md)：常用命令集合，适合实验现场快速复制。
- [docs/project_conventions_zh.md](project_conventions_zh.md)：Codex / AI agent 工程文件结构规约，用于约束后续新增文件、配置、脚本和文档的位置。

## 环境与路径

- [docs/setup_and_faq.md](setup_and_faq.md)：环境部署、常见问题和基础排错。
- [docs/data_sync.md](data_sync.md)：笔记本与主机之间的数据同步流程。
- [docs/host_data_share_setup.md](host_data_share_setup.md)：主机共享盘和 SMB 访问配置说明。

## 相机与采集

- [docs/laptop_lab_capture_workflow.md](laptop_lab_capture_workflow.md)：采集笔记本在实验室的推荐操作流程。
- [docs/camera_architecture_zh.md](camera_architecture_zh.md)：D455 / Hikrobot / Webcam 统一相机架构说明。
- [docs/camera_config_migration_zh.md](camera_config_migration_zh.md)：相机配置拆分与迁移说明。
- [docs/board_capture.md](board_capture.md)：标定板图像采集说明。

## 标定

- [docs/calibration_guide.md](calibration_guide.md)：标定总流程入口。
- [docs/camera_rigid_calibration.md](camera_rigid_calibration.md)：相机刚体到光学坐标系外参标定说明。
- [docs/hik_camera_calibration.md](hik_camera_calibration.md)：Hikrobot 工业相机内参 / 外参相关说明。
- [docs/fixed_camera_calibration.md](fixed_camera_calibration.md)：固定相机世界位姿相关说明。

## 动捕与自动标签

- [docs/mocap_label_generation.md](mocap_label_generation.md)：基于 FzMotion / Mocap CSV 自动生成 YOLO Pose 标签。
- [docs/custom_car_model.md](custom_car_model.md)：小车自定义关键点模型说明。

## YOLO Pose 训练

- [docs/training_guide.md](training_guide.md)：构建数据集、训练 YOLO Pose、检查训练结果的流程。

## Replay / PnP / Live Pose

- [docs/live_inference.md](live_inference.md)：实时推理与位姿显示说明。
- [docs/kalman_replay.md](kalman_replay.md)：离线 replay、PnP 与 Kalman 回放相关说明。

## Kalman / Tracking

- [docs/fast_moving_tracking.md](fast_moving_tracking.md)：Fast-Moving Object Tracking & Pose Estimation 总体方案。
- [docs/reliability_aware_kalman.md](reliability_aware_kalman.md)：可靠性自适应 Kalman 设计说明。
- [docs/kalman_replay.md](kalman_replay.md)：Kalman 回放验证入口。

## Evaluation / Ablation

- [docs/mocap_gt_evaluation.md](mocap_gt_evaluation.md)：Mocap 真值评估流程。

## 数据同步

- [docs/data_sync.md](data_sync.md)：采集笔记本到主机的数据同步说明。
- [docs/host_data_share_setup.md](host_data_share_setup.md)：主机共享目录配置说明。

## 色彩校正实验

- [docs/color_correction_zh.md](color_correction_zh.md)：Hikrobot 画面偏暗时的 HSV / RGB / Gamma 等色彩校正实验说明。

## 文献阅读

- 当前未发现专门的文献阅读入口文档；后续可以新增 `docs/literature_reading.md` 或按论文主题拆分。

## 过程记录与归档

- [docs/archive/README.md](archive/README.md)：阶段性验收报告、迁移记录、同步记录和历史过程文档的未来归档说明。
- [docs/logs/README.md](logs/README.md)：单日实验记录、自动生成命令快照和实验过程记录的未来归档说明。

## 当前阶段不要移动的核心脚本

当前阶段不要移动以下核心脚本：

- `scripts/capture_object_samples.py`
- `scripts/generate_mocap_labels.py`
- `scripts/solve_camera_rigid_to_optical.py`
- `scripts/verify_camera_rigid_to_optical.py`
- `scripts/calibrate_hik_camera.py`
- `scripts/prepare_yolo_pose_dataset.py`
- `scripts/train_ultralytics_pose.py`
- `scripts/run_live_pose.py`
- `scripts/smoke_replay_pipeline.py`
- `scripts/run_kalman_ablation.py`
- `scripts/evaluate_pose_results.py`

原因：这些脚本已经被当前 README、docs、实验命令和主机 / 笔记本流程引用，短期移动会破坏已验证流程。后续如果要整理脚本结构，应先新增兼容入口或 wrapper，再逐步迁移。
