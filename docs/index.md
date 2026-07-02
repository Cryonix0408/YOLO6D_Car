# YOLO6D_Car 文档索引

这是 `YOLO6D_Car` 项目的文档总入口。当前文档按主题分层整理，`docs/` 根目录长期只保留本索引、工程规约、`archive/`、`logs/` 和按主题划分的子目录。

## 项目总览与工程规约

- [project_conventions_zh.md](project_conventions_zh.md)：项目文件结构、命名、Git、数据管理和 Codex 协作规约。
- [architecture/project_guide.md](architecture/project_guide.md)：项目整体目标、数据流和模块关系。
- [architecture/camera_architecture_zh.md](architecture/camera_architecture_zh.md)：D455、Hikrobot、Webcam 的统一相机架构说明。
- [architecture/project_structure_audit_zh.md](architecture/project_structure_audit_zh.md)：项目结构审计记录。
- [architecture/project_redundancy_report_zh.md](architecture/project_redundancy_report_zh.md)：冗余文件和历史遗留内容分析。
- [architecture/project_structure_proposal_zh.md](architecture/project_structure_proposal_zh.md)：推荐目录结构设计。
- [architecture/project_structure_migration_plan_zh.md](architecture/project_structure_migration_plan_zh.md)：后续结构迁移计划。
- [architecture/configs_migration_plan_zh.md](architecture/configs_migration_plan_zh.md)：`configs/` 配置目录收口设计与兼容迁移方案。当前 configs 正处于复制兼容迁移阶段，新旧路径会短期并存。
- [architecture/configs_b2_compatibility_validation_zh.md](architecture/configs_b2_compatibility_validation_zh.md)：Phase B2 新旧配置路径兼容验证报告。
- [architecture/project_code_reading_guide.md](architecture/project_code_reading_guide.md)：读代码顺序和核心模块入口。
- [architecture/code_reading_notes.md](architecture/code_reading_notes.md)：代码阅读过程记录。

## 环境、路径与同步

- [setup/common_commands.md](setup/common_commands.md)：常用采集、标定、同步、训练、验证命令。
- [setup/setup_and_faq.md](setup/setup_and_faq.md)：环境部署和常见问题。
- [setup/host_data_share_setup.md](setup/host_data_share_setup.md)：主机共享盘配置说明。
- [setup/data_sync.md](setup/data_sync.md)：笔记本到主机的数据同步流程。
- [setup/pipeline_gdrive_workflow.md](setup/pipeline_gdrive_workflow.md)：主机 G 盘数据根目录工作流。
- [setup/glossary.md](setup/glossary.md)：项目术语表。

## 相机与采集

- [cameras/camera_config_migration_zh.md](cameras/camera_config_migration_zh.md)：相机配置迁移说明。
- [cameras/hikvision_parameter_presets.md](cameras/hikvision_parameter_presets.md)：Hikrobot 曝光、增益、帧率等参数预设。
- [capture/laptop_lab_capture_workflow.md](capture/laptop_lab_capture_workflow.md)：采集笔记本实验室采集流程。
- [capture/auto_object_capture.md](capture/auto_object_capture.md)：自动采集脚本说明。
- [capture/register_capture_session.md](capture/register_capture_session.md)：采集 session 注册流程。
- [capture/session_manifest_workflow.md](capture/session_manifest_workflow.md)：session manifest 记录规范。
- [capture/process_single_session.md](capture/process_single_session.md)：单个 session 后处理流程。
- [capture/full_pipeline_checklist.md](capture/full_pipeline_checklist.md)：完整实验流程检查表。
- [capture/full_workflow_dryrun.md](capture/full_workflow_dryrun.md)：离线 dry-run 验证流程。
- [capture/lab_execution_plan.md](capture/lab_execution_plan.md)：实验室执行计划。
- [capture/first_real_data_success_criteria.md](capture/first_real_data_success_criteria.md)：第一批真实数据成功标准。
- [capture/experiment_day_checklist_workflow.md](capture/experiment_day_checklist_workflow.md)：实验当天检查清单。

## 标定

- [calibration/calibration_guide.md](calibration/calibration_guide.md)：标定总流程。
- [calibration/camera_rigid_calibration.md](calibration/camera_rigid_calibration.md)：相机刚体到光心外参标定。
- [calibration/hik_camera_calibration.md](calibration/hik_camera_calibration.md)：Hikrobot 相机内参与外参标定。
- [calibration/fixed_camera_calibration.md](calibration/fixed_camera_calibration.md)：固定相机世界位姿说明。
- [calibration/board_capture.md](calibration/board_capture.md)：标定板采集说明。

## 动捕与自动标签

- [labeling/mocap_label_generation.md](labeling/mocap_label_generation.md)：FzMotion / Mocap 自动生成 YOLO Pose 标签。
- [labeling/visualize_auto_labels.md](labeling/visualize_auto_labels.md)：自动标签 overlay 可视化检查。
- [labeling/mocap_csv_quality_check.md](labeling/mocap_csv_quality_check.md)：动捕 CSV 质量检查。
- [labeling/custom_car_model.md](labeling/custom_car_model.md)：小车自定义关键点模型说明。

## YOLO Pose 训练

- [training/training_guide.md](training/training_guide.md)：YOLO Pose 数据集构建和训练流程。
- [training/dataset_and_model_management.md](training/dataset_and_model_management.md)：dataset / model 版本管理。

## Replay / PnP / Live Pose / Kalman

- [tracking/live_inference.md](tracking/live_inference.md)：实时推理和可视化。
- [tracking/fast_moving_tracking.md](tracking/fast_moving_tracking.md)：Fast-Moving Object Tracking & Pose Estimation 方案。
- [tracking/kalman_replay.md](tracking/kalman_replay.md)：Kalman replay 流程。
- [tracking/reliability_aware_kalman.md](tracking/reliability_aware_kalman.md)：可靠性加权 Kalman 方案。
- [tracking/kalman_ablation_workflow.md](tracking/kalman_ablation_workflow.md)：Kalman 消融实验流程。

## Evaluation / Ablation

- [evaluation/mocap_gt_evaluation.md](evaluation/mocap_gt_evaluation.md)：基于动捕 GT 的位姿评估。
- [evaluation/evaluate_pose_results.md](evaluation/evaluate_pose_results.md)：位姿结果评估脚本说明。

## 色彩校正实验

- [experiments/color_correction_zh.md](experiments/color_correction_zh.md)：基于 HSV / Gamma / RGB gain / CCM 的离线色彩校正原型。

## 文献阅读

当前 `docs/literature/` 下暂无文献阅读文档。后续 Fast-Moving、Kalman、PnP、6DoF Pose 论文笔记建议放在这里。

## 过程记录与归档

- [archive/README.md](archive/README.md)：阶段性验收报告、迁移记录、同步记录和历史过程文档说明。
- [logs/README.md](logs/README.md)：单日实验记录、命令快照和实验过程日志说明。

## 当前阶段不要移动的核心入口

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

原因：这些脚本已经被当前 README、docs、实验命令和主机/笔记本流程引用，短期移动会破坏已验证流程。后续如果要迁移，应单独开一次结构迁移任务，并同步更新命令、文档和 smoke test。
