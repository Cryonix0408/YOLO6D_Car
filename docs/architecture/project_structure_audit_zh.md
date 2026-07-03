# YOLO6D_Car 项目结构审计报告

生成日期：2026-07-01  
当前项目路径：`D:\YOLO6D_Car`  
当前 Git 分支：`codex/color-correction-prototype`

本报告只做只读扫描和结构分析，不代表已经执行移动、删除或重构。

## 1. 当前目录总览

| 目录 | 当前用途 | 文件类型 | 是否核心 | 是否应进入 Git | 备注 |
| -- | -- | -- | -- | -- | -- |
| `src/` | Python 源码根目录 | 代码 | 是 | 是 | 主业务逻辑位于 `src/yolo6d_car/` |
| `src/yolo6d_car/camera/` | D455、Hikrobot、Webcam 相机后端和统一 factory | 代码 | 是 | 是 | 已开始统一相机架构 |
| `src/yolo6d_car/calibration/` | Hik 相机内参标定、棋盘格检测、标定质量 | 代码 | 是 | 是 | 和 `scripts/calibrate_hik_camera.py` 绑定 |
| `src/yolo6d_car/mocap/` | FzMotion CSV 读取和刚体插值 | 代码 | 是 | 是 | 自动标签和 GT evaluation 的基础 |
| `src/yolo6d_car/pose/` | PnP、YOLO 接口、基础时间滤波 | 代码 | 是 | 是 | 6DoF 位姿恢复核心 |
| `src/yolo6d_car/tracking/` | fixed KF、reliability-aware KF、gating、状态机 | 代码 | 是 | 是 | fast-moving 阶段核心 |
| `src/yolo6d_car/evaluation/` | 轨迹指标、GT 对比、报告 | 代码 | 是 | 是 | 需要真实数据继续验证 |
| `src/yolo6d_car/image_processing/` | HSV/颜色校正实验模块 | 代码 | 部分 | 是 | 当前是新实验性模块 |
| `scripts/` | 命令行入口脚本 | 代码/工具 | 是 | 是 | 主流程、调试、同步脚本混放 |
| `configs/` | 配置文件 | 配置 | 是 | 是 | 根目录旧配置与子目录新配置并存 |
| `configs/cameras/` | 相机硬件配置 | 配置 | 是 | 是 | D455/Hik/Webcam 分离较清楚 |
| `configs/capture/` | 自动采集配置 | 配置 | 是 | 是 | 新架构推荐入口 |
| `configs/calibration/` | 新式标定配置 | 配置 | 是 | 是 | 根目录仍有旧版 `calibration_hik_*.yaml` |
| `docs/` | 项目说明、流程、实验记录 | 文档 | 是 | 是 | 文档数量较多，需要索引和归档 |
| `data/examples/` | 小型示例数据和 smoke test 数据 | 小数据 | 是 | 是 | `.gitignore` 明确保留 |
| `models/` | 关键点模型 JSON | 配置/模型定义 | 是 | 是 | 只应放小 JSON，不应放权重 |
| `outputs/` | 自动标签、训练输出、标定输出等 | 大数据 | 否 | 否 | 已在 `.gitignore`，仓库中仍存在本地目录 |
| `results/` | 评估、质量检查、可视化输出 | 大数据 | 否 | 否 | 已在 `.gitignore` |
| `logs/` | 日志 | 大数据 | 否 | 否 | 已在 `.gitignore` |
| `FZmotion_Data/` | 动捕 CSV 原始数据 | 大数据 | 否 | 否 | 已在 `.gitignore` |
| `tools/` | 文档/报告/PPT 生成辅助工具 | 工具 | 部分 | 是 | 部分工具偏一次性，可后续归档 |
| `.idea/` | IDE 配置 | 本地环境 | 否 | 否 | 已部分 ignore，但目录存在 |

## 2. 当前脚本清单

| 脚本 | 作用 | 所属阶段 | 是否主流程 | 是否调试工具 | 是否可能冗余 | 建议 |
| -- | -- | -- | -- | -- | -- | -- |
| `activate_yolo6d_env.ps1` | 激活环境辅助 | environment | 否 | 否 | 否 | keep |
| `archive_train_run.py` | 训练结果归档 | model management | 否 | 否 | 低 | keep |
| `batch_generate_mocap_labels.py` | 批量生成 mocap 标签 | label generation | 是 | 否 | 否 | keep |
| `build_custom_model_from_csv.py` | 从 marker CSV 构建车体关键点模型 | camera calibration | 是 | 否 | 否 | keep |
| `calibrate_hik_camera.py` | Hik 内参标定 | camera calibration | 是 | 否 | 否 | keep |
| `capture_board_samples.py` | D455 标定板采集 | camera calibration | 部分 | 否 | 中 | keep for D455 legacy |
| `capture_object_samples.py` | 统一相机对象采集入口 | data capture | 是 | 否 | 否 | keep |
| `check_capture_quality.py` | 采集质量检查 | data capture | 是 | 否 | 否 | keep |
| `check_host_share_ready.py` | 主机共享盘检查 | sync / transfer | 否 | 否 | 否 | keep |
| `check_mocap_csv.py` | 动捕 CSV 质量检查 | mocap check | 是 | 否 | 否 | keep |
| `check_project_readiness.py` | 项目准备状态检查 | environment | 否 | 否 | 否 | keep |
| `collect_hikvision_sequence.py` | Hik 连续帧采集 | data capture | 部分 | 否 | 中 | 与 `capture_object_samples.py` 边界需说明 |
| `compute_static_camera_pose.py` | 固定相机位姿计算 | camera calibration | 部分 | 否 | 中 | legacy/utility |
| `dryrun_full_workflow.py` | 全流程 dry-run | debug / prototype | 否 | 是 | 中 | 可移到 `scripts/dev/` |
| `evaluate_pose_results.py` | 位姿结果评估 | evaluation | 是 | 否 | 否 | keep |
| `export_ultralytics_pose_to_replay.py` | YOLO 预测导出 replay | replay | 是 | 否 | 否 | keep |
| `generate_experiment_day_checklist.py` | 实验日清单生成 | session management | 否 | 否 | 中 | keep or docs tool |
| `generate_mocap_labels.py` | 单 session 自动标签 | label generation | 是 | 否 | 否 | keep |
| `manage_datasets.py` | dataset manifest 管理 | dataset management | 是 | 否 | 否 | keep |
| `manage_models.py` | model registry 管理 | model management | 是 | 否 | 否 | keep |
| `manage_sessions.py` | session manifest 管理 | session management | 是 | 否 | 否 | keep |
| `migrate_rigid_frame_from_csv.py` | 刚体坐标迁移 | camera calibration | 部分 | 否 | 中 | utility，需文档化 |
| `prepare_yolo_pose_dataset.py` | 构建 YOLO Pose 数据集 | dataset preparation | 是 | 否 | 否 | keep |
| `print_lab_commands.py` | 打印实验室命令 | debug / prototype | 否 | 是 | 中 | 可归入 dev/docs |
| `process_single_session.py` | 单 session 流水线处理 | session management | 是 | 否 | 否 | keep |
| `refine_camera_rigid_to_optical_from_sessions.py` | 多 session 优化外参 | camera calibration | 部分 | 否 | 中 | advanced utility |
| `register_capture_session.py` | 注册采集 session | session management | 是 | 否 | 否 | keep |
| `run_kalman_ablation.py` | Kalman 消融实验 | ablation | 是 | 否 | 否 | keep |
| `run_live_pose.py` | 实时位姿推理 | live pose | 是 | 否 | 否 | keep |
| `run_pipeline.py` | 通用 pipeline 入口 | replay | 部分 | 否 | 中 | 需明确与 smoke/live 的边界 |
| `smoke_replay_pipeline.py` | 离线 smoke replay | replay | 是 | 否 | 否 | keep |
| `solve_camera_rigid_to_optical.py` | ArUco + mocap 解相机外参 | camera calibration | 是 | 否 | 否 | keep |
| `sync_capture_batch_to_host.py` | 批量同步采集数据到主机 | sync / transfer | 是 | 否 | 否 | keep |
| `sync_capture_to_host.py` | 单 session 同步 | sync / transfer | 是 | 否 | 中 | 与 batch 脚本边界需说明 |
| `test_color_correction.py` | 颜色校正测试 | debug / prototype | 否 | 是 | 中 | 实验期 keep，后续进 dev |
| `test_hikvision_camera.py` | Hik 相机预览/参数测试 | data capture | 是 | 是 | 否 | keep |
| `train_ultralytics_pose.py` | YOLO Pose 训练 | training | 是 | 否 | 否 | keep |
| `verify_camera_rigid_to_optical.py` | 外参投影验证 | camera calibration | 是 | 否 | 否 | keep |
| `visualize_auto_labels.py` | 标签可视化 | label generation | 是 | 否 | 否 | keep |
| `visualize_hikvision_sequence.py` | Hik 采集序列可视化 | data capture | 部分 | 是 | 中 | utility |

## 3. 当前配置清单

| 配置文件 | 作用 | 所属模块 | 是否主配置 | 是否旧配置 | 是否可归档 | 建议 |
| -- | -- | -- | -- | -- | -- | -- |
| `configs/paths_local.yaml` | 主机路径配置 | paths | 是 | 否 | 否 | keep |
| `configs/paths_laptop.yaml` | 笔记本路径配置 | paths | 是 | 否 | 否 | keep |
| `configs/cameras/d455.yaml` | D455 相机参数 | camera | 是 | 否 | 否 | keep |
| `configs/cameras/hik_6mm.yaml` | Hik 6mm 相机参数 | camera | 是 | 否 | 否 | keep |
| `configs/cameras/hik_8mm.yaml` | Hik 8mm 相机参数 | camera | 是 | 否 | 否 | keep |
| `configs/cameras/webcam.yaml` | Webcam 参数 | camera | 否 | 否 | 否 | keep |
| `configs/capture/d455_object_capture_auto.yaml` | D455 自动采集 | capture | 是 | 否 | 否 | keep |
| `configs/capture/hik_6mm_object_capture_auto.yaml` | Hik 6mm 自动采集 | capture | 是 | 否 | 否 | keep |
| `configs/capture/hik_8mm_object_capture_auto.yaml` | Hik 8mm 自动采集 | capture | 是 | 否 | 否 | keep |
| `configs/calibration/hik_6mm_calibration.yaml` | Hik 6mm 内参标定 | calibration | 是 | 否 | 否 | keep |
| `configs/calibration/hik_8mm_calibration.yaml` | Hik 8mm 内参标定 | calibration | 是 | 否 | 否 | keep |
| `configs/calibration/d455_rgb_calibration.yaml` | D455 RGB 内参标定 | calibration | 是 | 否 | 否 | keep |
| `configs/calibration_hik_6mm.yaml` | 旧路径 Hik 6mm 内参标定 | calibration | 否 | 是 | 是 | keep temporarily |
| `configs/calibration_hik_8mm.yaml` | 旧路径 Hik 8mm 内参标定 | calibration | 否 | 是 | 是 | keep temporarily |
| `configs/fzmotion_hikvision_6mm_current_rigids.yaml` | Hik 6mm 动捕/外参标签配置 | labeling | 是 | 否 | 否 | keep |
| `configs/fzmotion_fixed_camera_current_rigids.yaml` | D455 当前刚体配置 | labeling | 是 | 否 | 否 | keep |
| `configs/fzmotion_fixed_camera_current_rigids_gdrive.yaml` | 主机/G 盘版本 | labeling | 部分 | 否 | 中 | 可纳入 paths 机制 |
| `configs/fzmotion_fixed_camera_live_v1.yaml` | D455 实时推理配置 | live pose | 是 | 否 | 否 | keep |
| `configs/fzmotion_fast_moving_live.yaml` | fast-moving live 配置 | live pose | 是 | 否 | 否 | keep |
| `configs/kalman_fixed.yaml` | fixed KF 配置 | tracking | 是 | 否 | 否 | keep |
| `configs/kalman_reliability.yaml` | reliability-aware KF 配置 | tracking | 是 | 否 | 否 | keep |
| `configs/local_smoke_replay.yaml` | 本地 smoke replay | replay | 是 | 否 | 否 | keep |
| `configs/session_manifest_template.yaml` | session manifest 模板 | session management | 是 | 否 | 否 | keep |
| `configs/dataset_manifest_template.yaml` | dataset manifest 模板 | dataset management | 是 | 否 | 否 | keep |
| `configs/model_registry_template.yaml` | 模型注册模板 | model management | 是 | 否 | 否 | keep |
| `configs/uav_4m_20_sessions.yaml` | 旧 20-session 数据集 manifest | dataset | 部分 | 是 | 中 | archive after v1 freeze |
| `configs/uav_4m_20_sessions_gdrive.yaml` | 主机/G 盘 20-session manifest | dataset | 部分 | 否 | 中 | 保留到数据迁移稳定后 |
| `configs/board_capture.yaml` | D455 标定板采集旧配置 | calibration | 部分 | 是 | 中 | keep for D455 legacy |
| `configs/object_capture.yaml` | 旧对象采集配置 | capture | 否 | 是 | 是 | archive candidate |
| `configs/object_capture_auto.yaml` | 自动对象采集旧入口 | capture | 部分 | 是 | 中 | keep temporarily |
| `configs/hikvision_capture_presets.yaml` | Hik 曝光/采集参数预设 | capture | 是 | 否 | 否 | keep |
| `configs/color_correction/rgb_wall_reference.yaml` | HSV/颜色校正实验 | image processing | 部分 | 否 | 否 | keep experimental |

## 4. 当前源码模块清单

| 模块 | 作用 | 当前状态 | 被哪些脚本调用 | 是否核心 | 是否需要重构 | 建议 |
| -- | -- | -- | -- | -- | -- | -- |
| `camera/base_camera.py` | 统一 CameraFrame/BaseCamera 接口 | Done | `capture_object_samples.py` 等 | 是 | 低 | keep |
| `camera/factory.py` | 根据配置创建相机后端 | Done | `capture_object_samples.py` | 是 | 低 | keep |
| `camera/d455.py` | RealSense D455 后端 | Done | 采集/旧流程 | 是 | 中 | 保持兼容 |
| `camera/hikvision_camera.py` | Hik MVS 原始后端 | Done | Hik 测试/stream | 是 | 中 | 后续与 stream 边界需说明 |
| `camera/hikvision_stream.py` | Hik 统一接口适配 | Done | 新采集流程 | 是 | 低 | keep |
| `camera/webcam.py` | Webcam 后端 | Partial | validate/smoke | 否 | 低 | keep |
| `calibration/*` | 内参标定与质量控制 | Done/Partial | `calibrate_hik_camera.py` | 是 | 低 | keep |
| `mocap/csv_provider.py` | FzMotion CSV Provider | Done | label/evaluation | 是 | 中 | 需要性能优化但不要急改 |
| `pose/pnp.py` | PnP 位姿恢复 | Done | pipeline/live | 是 | 低 | keep |
| `pose/yolo6d_interface.py` | YOLO Pose 接口 | Done | replay/live/export | 是 | 中 | 与 ultralytics 版本绑定需记录 |
| `tracking/*` | Kalman、reliability、gating | Partial | ablation/live | 是 | 中 | 需真实数据验证 |
| `evaluation/*` | 轨迹和 GT 指标 | Partial | evaluate scripts | 是 | 中 | 需真实数据验证 |
| `image_processing/color_correction.py` | HSV/颜色校正 | Prototype | `test_color_correction.py` | 否 | 中 | 实验稳定后再纳入主流程 |
| `path_utils.py` | data_root 路径解析 | Done | 多数脚本 | 是 | 低 | keep |
| `config.py` | 旧 pipeline 配置解析 | Done | label/live/replay | 是 | 中 | 旧配置兼容核心，不宜乱动 |
| `pipeline.py` | 推理 pipeline | Done/Partial | replay/live | 是 | 中 | 后续抽象输入输出 |
| `session_manifest.py` | session manifest | Done | management/process | 是 | 低 | keep |
| `dataset_manifest.py` | dataset manifest | Done | management | 是 | 低 | keep |
| `model_registry.py` | 模型注册 | Done | management | 是 | 低 | keep |

## 5. 当前文档清单

| 文档 | 作用 | 是否核心文档 | 是否过程记录 | 是否可归档 | 建议 |
| -- | -- | -- | -- | -- | -- |
| `README.md` | 项目总入口 | 是 | 否 | 否 | 保持简洁，链接到 docs index |
| `project_guide.md` | 项目总览 | 是 | 否 | 否 | 可作为核心文档 |
| `common_commands.md` | 常用命令 | 是 | 否 | 否 | 实验室高频入口 |
| `laptop_lab_capture_workflow.md` | 笔记本采集流程 | 是 | 否 | 否 | 当前实验核心 |
| `camera_architecture_zh.md` | 相机架构说明 | 是 | 否 | 否 | 保留 |
| `camera_config_migration_zh.md` | 相机配置迁移说明 | 部分 | 是 | 中 | 迁移完成后归档 |
| `camera_phase1_acceptance_report_zh.md` | phase1 验收报告 | 否 | 是 | 是 | archive candidate |
| `camera_phase1_sync_notes_zh.md` | phase1 同步说明 | 否 | 是 | 是 | archive candidate |
| `calibration_guide.md` | 标定入口 | 是 | 否 | 否 | 保留 |
| `camera_rigid_calibration.md` | 相机刚体外参 | 是 | 否 | 否 | 保留 |
| `hik_camera_calibration.md` | Hik 内参标定 | 是 | 否 | 否 | 保留 |
| `mocap_label_generation.md` | mocap 自动标签 | 是 | 否 | 否 | 保留 |
| `training_guide.md` | 训练说明 | 是 | 否 | 否 | 保留 |
| `fast_moving_tracking.md` | fast-moving 设计 | 是 | 否 | 否 | 保留 |
| `kalman_replay.md` | Kalman replay | 是 | 否 | 否 | 保留 |
| `reliability_aware_kalman.md` | reliability-aware KF | 是 | 否 | 否 | 保留 |
| `mocap_gt_evaluation.md` | GT evaluation | 是 | 否 | 否 | 保留 |
| `data_sync.md` | 数据同步 | 是 | 否 | 否 | 保留 |
| `host_data_share_setup.md` | 主机共享设置 | 是 | 否 | 否 | 保留 |
| `path_migration_audit.md` | 路径迁移审计 | 否 | 是 | 是 | archive candidate |
| `lab_commands_generated.md` | 自动生成命令 | 否 | 是 | 是 | archive candidate |
| `experiment_day_2026-05-30.md` | 单日实验记录 | 否 | 是 | 是 | archive/log candidate |
| `build_first_then_execute_plan.md` | 阶段计划 | 否 | 是 | 是 | archive candidate |
| `color_correction_zh.md` | 颜色校正实验 | 部分 | 是 | 否 | 实验期保留 |

完整文档数量较多，建议下一阶段新增 `docs/index.md`，把核心文档、实验流程、过程记录、归档文档分层。

