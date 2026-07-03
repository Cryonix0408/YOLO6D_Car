# YOLO6D_Car Scripts 脚本盘点与分类

本文档是 Phase C1 的脚本盘点结果。当前 `scripts/` 仍是项目命令入口目录，里面同时包含采集、标定、标签、训练、replay、Kalman、评估、同步、管理和实验性工具。

本轮只做盘点和分类，不移动、不删除、不重命名任何脚本。短期为了兼容 README、docs、主机和笔记本上的旧命令，核心脚本继续保留在 `scripts/` 根目录。后续如果要迁移，应先做 wrapper 化，再逐步把真实实现移入分类目录或 `src/yolo6d_car/cli/`。

## 1. 当前 scripts 总览

- 当前阶段 `scripts/` 还没有真正分层。
- 本轮只建立脚本清单和迁移建议。
- 后续可考虑新增分类目录，但不能为了视觉干净直接移动核心脚本。
- 新增脚本从现在开始应先判断属于正式流程、同步、管理、实验、debug 还是 legacy。

## 2. 脚本分类总表

| 脚本 | 类型 | 所属阶段 | 是否主流程 | 是否硬件相关 | 是否可安全运行 --help | 是否建议短期移动 | 建议未来位置 | 备注 |
| -- | -- | ---- | ----- | ------ | -------------- | -------- | ------ | -- |
| `activate_yolo6d_env.ps1` | utility | environment | partial | no | no | maybe later | scripts/dev/ | PowerShell 环境辅助脚本，当前含本机环境路径。 |
| `archive_train_run.py` | management | model management | partial | no | yes | maybe later | scripts/management/ | 归档训练权重和元信息。 |
| `batch_generate_mocap_labels.py` | core | label generation | yes | no | yes | no | scripts/labeling/ | 多 session 批量自动标签入口。 |
| `build_custom_model_from_csv.py` | utility | label generation | partial | no | yes | maybe later | scripts/labeling/ | 从动捕 marker CSV 构建自定义关键点模型。 |
| `calibrate_hik_camera.py` | core | camera calibration | yes | possible | yes | no | scripts/calibration/ | Hikrobot 内参采集与标定入口；正式运行会连接相机。 |
| `capture_board_samples.py` | core | camera calibration | yes | yes | yes | no | scripts/calibration/ | D455 标定板采集入口。 |
| `capture_object_samples.py` | core | camera capture | yes | yes | yes | no | scripts/capture/ | D455/Hik/Webcam 物体采集核心入口。 |
| `check_capture_quality.py` | utility | camera capture | partial | no | yes | maybe later | scripts/capture/ | 检查采集 session 是否适合标签和训练。 |
| `check_host_share_ready.py` | sync | sync / transfer | no | no | yes | yes to sync | scripts/sync/ | 主机共享盘可用性检查，含主机数据根路径默认值。 |
| `check_mocap_csv.py` | utility | mocap check | partial | no | yes | maybe later | scripts/labeling/ | 动捕 CSV 质量检查。 |
| `check_project_readiness.py` | utility | environment | partial | no | yes | maybe later | scripts/dev/ | 离线检查依赖、环境和关键文件。 |
| `collect_hikvision_sequence.py` | core | camera capture | partial | yes | yes | no | scripts/capture/ | Hikrobot 连续帧采集；正式运行会连接相机。 |
| `compute_static_camera_pose.py` | utility | camera calibration | partial | no | yes | maybe later | scripts/calibration/ | 根据标定样本计算固定相机位姿。 |
| `dryrun_full_workflow.py` | debug | debug / prototype | no | no | yes | yes to dev | scripts/dev/ | 生成完整流程 dry-run 命令和检查报告。 |
| `evaluate_pose_results.py` | core | evaluation | yes | no | yes | no | scripts/evaluation/ | 位姿结果和滤波效果评估。 |
| `export_ultralytics_pose_to_replay.py` | utility | replay | partial | no | yes | maybe later | scripts/replay/ | 将 Ultralytics Pose 预测导出为 replay JSON。 |
| `generate_experiment_day_checklist.py` | utility | environment | no | no | yes | yes to dev | scripts/dev/ | 生成实验日 Markdown 检查清单。 |
| `generate_mocap_labels.py` | core | label generation | yes | no | yes | no | scripts/labeling/ | Mocap 投影自动生成 YOLO Pose 标签核心入口。 |
| `manage_datasets.py` | management | dataset management | partial | no | yes | maybe later | scripts/management/ | dataset manifest 管理和 YOLO dataset.yaml 生成。 |
| `manage_models.py` | management | model management | partial | no | yes | maybe later | scripts/management/ | model registry 管理。 |
| `manage_sessions.py` | management | session management | partial | no | yes | maybe later | scripts/management/ | session manifest 管理和 ablation 命令生成。 |
| `migrate_rigid_frame_from_csv.py` | utility | camera calibration | partial | no | yes | maybe later | scripts/calibration/ | 新旧刚体坐标系迁移辅助。 |
| `prepare_yolo_pose_dataset.py` | core | dataset preparation | yes | no | yes | no | scripts/dataset/ | 从 auto labels 构建 YOLO Pose 数据集。 |
| `print_lab_commands.py` | debug | debug / prototype | no | no | yes | yes to dev | scripts/dev/ | 打印实验室命令，不执行。 |
| `process_single_session.py` | management | session management | partial | no | yes | maybe later | scripts/management/ | 单 session 质量检查、标签和 replay 配置流程编排。 |
| `refine_camera_rigid_to_optical_from_sessions.py` | utility | camera calibration | partial | no | yes | maybe later | scripts/calibration/ | 使用多 session YOLO 关键点优化相机刚体外参。 |
| `register_capture_session.py` | management | session management | partial | no | yes | maybe later | scripts/management/ | 将采集目录注册为 session manifest 条目。 |
| `run_kalman_ablation.py` | core | ablation | yes | no | yes | no | scripts/tracking/ | raw PnP / fixed KF / reliability-aware KF 消融。 |
| `run_live_pose.py` | core | live pose | yes | possible | yes | no | scripts/replay/ | 实机实时推理入口，正式运行可能依赖相机/模型。 |
| `run_pipeline.py` | legacy | unknown | unknown | unknown | unknown | yes to legacy | scripts/legacy/ | 极简入口，需后续确认是否仍有引用。 |
| `smoke_replay_pipeline.py` | core | replay | yes | no | yes | no | scripts/replay/ | 离线 replay smoke test，不打开 D455 或 GUI。 |
| `solve_camera_rigid_to_optical.py` | core | camera calibration | yes | no | yes | no | scripts/calibration/ | ArUco + Mocap 求解相机刚体到光心外参。 |
| `sync_capture_batch_to_host.py` | sync | sync / transfer | partial | no | yes | yes to sync | scripts/sync/ | 批量同步多个采集 session 到主机共享盘。 |
| `sync_capture_to_host.py` | sync | sync / transfer | partial | no | yes | yes to sync | scripts/sync/ | 单 session 增量同步，避免覆盖主机已有文件。 |
| `test_color_correction.py` | prototype | image processing | no | no | yes | yes to dev | scripts/dev/ | 离线色彩校正 prototype，不接正式 pipeline。 |
| `test_hikvision_camera.py` | debug | camera capture | no | yes | yes | yes to dev | scripts/dev/ | Hikrobot 相机预览测试；正式运行会连接相机。 |
| `train_ultralytics_pose.py` | core | training | yes | no | yes | no | scripts/training/ | YOLO Pose 训练入口；不要在整理阶段运行训练。 |
| `verify_camera_rigid_to_optical.py` | core | camera calibration | yes | no | yes | no | scripts/calibration/ | 通过标定板重投影验证相机外参。 |
| `visualize_auto_labels.py` | utility | label generation | partial | no | yes | maybe later | scripts/labeling/ | 可视化检查 YOLO Pose 自动标签。 |
| `visualize_hikvision_sequence.py` | debug | debug / prototype | no | no | yes | yes to dev | scripts/dev/ | 预览和统计 Hikrobot 已采集序列，不运行 YOLO。 |

## 3. 当前必须保留在 scripts 根目录的核心脚本

以下脚本短期不要移动：

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

原因：

- README / docs / 实验命令仍引用这些路径。
- 主机和笔记本流程依赖这些旧入口。
- 直接移动会破坏已验证命令。
- 后续如果移动，应先保留根目录 wrapper，再迁移真实实现。

## 4. 可以优先归入 scripts/dev 的候选

| 脚本 | 当前用途 | 为什么偏 dev/prototype | 是否建议现在移动 | 风险 |
| -- | ---- | ------------------ | -------- | -- |
| `dryrun_full_workflow.py` | 生成全流程 dry-run 命令和报告 | 实验前辅助，不是正式 pipeline 必经入口 | 否，本轮只列候选 | 文档可能仍引用旧路径。 |
| `generate_experiment_day_checklist.py` | 生成实验日检查清单 | 一次性/辅助型文档生成工具 | 否，本轮只列候选 | 含主机 G 盘示例路径，迁移前需同步文档。 |
| `print_lab_commands.py` | 打印实验室命令 | 命令生成器，不执行主流程 | 否，本轮只列候选 | 可能被实验流程文档引用。 |
| `test_color_correction.py` | 离线色彩校正 prototype | 明确实验性，不接正式 pipeline | 否，本轮只列候选 | 最近刚独立提交，短期不应混入正式流程。 |
| `test_hikvision_camera.py` | Hikrobot 相机预览测试 | 测试/调参工具，运行会连接硬件 | 否，本轮只列候选 | 移动会影响现场常用命令。 |
| `visualize_hikvision_sequence.py` | 可视化已采集 Hikrobot 序列 | 调试/检查工具，不运行 YOLO | 否，本轮只列候选 | 可保留到采集流程稳定后再迁移。 |
| `check_project_readiness.py` | 离线项目 readiness 检查 | 环境诊断工具，非正式 pipeline 阶段 | 否，本轮只列候选 | 可能用于新机器验收。 |

## 5. sync / transfer 脚本

| 脚本 | 用途 | 单 session / batch / check | 建议未来位置 | 是否主流程 |
| -- | -- | ------------------------- | ------ | ----- |
| `check_host_share_ready.py` | 检查主机共享盘、目录和网络访问状态 | check | scripts/sync/ | no |
| `sync_capture_to_host.py` | 将单个本地采集 session 增量同步到主机共享盘 | single session | scripts/sync/ | partial |
| `sync_capture_batch_to_host.py` | 批量扫描本地采集目录并同步多个 session | batch | scripts/sync/ | partial |

## 6. management 脚本

| 脚本 | 管理对象 | 说明 | 建议未来位置 |
| -- | -- | -- | -- |
| `manage_sessions.py` | session manifest | 校验 session 清单、过滤 session、生成 ablation 命令。 | scripts/management/ |
| `manage_datasets.py` | dataset manifest | 校验 dataset manifest，并生成 Ultralytics YOLO Pose dataset.yaml。 | scripts/management/ |
| `manage_models.py` | model registry | 校验模型注册表、列出和解析模型条目。 | scripts/management/ |
| `register_capture_session.py` | session manifest | 将采集目录注册为 session 条目。 | scripts/management/ |
| `process_single_session.py` | session workflow | 编排单 session 的质量检查、标签生成和 replay 配置。 | scripts/management/ |
| `archive_train_run.py` | model registry / train run | 归档训练权重和元数据。 | scripts/management/ |

## 7. scripts 工程化目标结构

长期目标可以整理为：

```text
scripts/
├── README.md
├── capture_object_samples.py              # legacy-compatible wrapper
├── generate_mocap_labels.py               # legacy-compatible wrapper
├── solve_camera_rigid_to_optical.py        # legacy-compatible wrapper
├── train_ultralytics_pose.py              # legacy-compatible wrapper
├── smoke_replay_pipeline.py               # legacy-compatible wrapper
├── capture/
├── calibration/
├── labeling/
├── dataset/
├── training/
├── replay/
├── tracking/
├── evaluation/
├── management/
├── sync/
├── dev/
└── legacy/
```

建议原则：

- 根目录保留高频兼容 wrapper。
- 真实逻辑未来可以逐步移动到 `src/yolo6d_car/cli/`。
- 短期不要直接移动核心脚本。
- 新增脚本从现在开始按分类放入子目录。

## 8. 后续迁移路线

### Phase C1：盘点脚本

当前阶段，只生成 inventory 和 README，不移动脚本。

### Phase C2：新增脚本按新目录放

未来新增实验性脚本放 `scripts/dev/`。新增同步脚本放 `scripts/sync/`。新增正式流程脚本需要先确认是否放根目录或子目录。

### Phase C3：低风险 dev 脚本迁移

把明显 prototype/debug 脚本移动到 `scripts/dev/`，但迁移前必须确认没有 README、docs、实验命令或主机/笔记本流程引用。

### Phase C4：核心脚本 wrapper 化

根目录脚本保留 wrapper，真实实现迁移到：

```text
src/yolo6d_car/cli/
```

### Phase C5：legacy 脚本归档

旧实验脚本进入 `scripts/legacy/`，删除必须人工确认。

## 9. 当前风险清单

- 移动脚本会破坏 README / docs 中的旧命令。
- 主机和笔记本同步流程可能依赖旧脚本路径。
- 有些脚本会隐式连接相机，例如 `capture_object_samples.py`、`test_hikvision_camera.py`、`collect_hikvision_sequence.py`。
- 有些脚本会写大量输出，例如采集、标签生成、训练和批量同步脚本。
- 有些脚本依赖当前 configs 路径，尤其是刚完成兼容迁移的配置。
- `test_color_correction.py` 目前是 prototype，不应接入正式 pipeline。
- 训练脚本不要在整理阶段运行。

## 10. 下一轮建议

下一轮最安全任务建议是：

```text
Phase C2：新增脚本按新目录放，并补充 scripts/README.md 中的新增脚本规则。
```

如果要进入迁移，建议先做只读引用检查，确认 README、docs 和常用命令中没有引用目标脚本后，再考虑：

```text
Phase C3：只移动明确 dev/prototype 的脚本到 scripts/dev/
```

目前不建议移动核心脚本。项目还处在实验室采集和主机/笔记本双端协同阶段，保持旧入口稳定比目录视觉整洁更重要。
