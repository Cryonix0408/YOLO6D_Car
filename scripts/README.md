# scripts 命令入口说明

`scripts/` 是 YOLO6D_Car 当前的命令行入口目录。这里包含采集、标定、自动标签、数据集构建、训练、replay、Kalman、评估、同步和实验性工具。

当前阶段为了兼容 README、docs、实验命令、主机和笔记本流程，不直接移动核心脚本。详细盘点和迁移建议见：

- [../docs/architecture/scripts_inventory_zh.md](../docs/architecture/scripts_inventory_zh.md)
- [../docs/project_conventions_zh.md](../docs/project_conventions_zh.md)

## Phase C2 子目录规则

Phase C2 只落地未来新增脚本的目录规则，不移动任何现有脚本。

- 旧核心脚本仍保留在 `scripts/` 根目录，短期不要移动。
- 新增临时 / prototype / debug 脚本应优先放 `scripts/dev/`。
- 新增同步 / 传输 / 主机共享检查脚本应优先放 `scripts/sync/`。
- 新增 session / dataset / model 管理脚本应优先放 `scripts/management/`。
- `scripts/legacy/` 只用于人工确认后的历史脚本，不自动归档、不自动删除。
- 不要随意在 `scripts/` 根目录新增 one-off 脚本。

如果未来确实要迁移旧脚本，应先检查 README、docs、主机和笔记本流程中的旧路径引用，并优先保留根目录 wrapper。

## 常用核心入口

### 采集

- `capture_object_samples.py`：D455 / Hikrobot / Webcam 物体采集入口。
- `capture_board_samples.py`：D455 标定板采集入口。
- `collect_hikvision_sequence.py`：Hikrobot 连续帧采集入口。

### 标定

- `calibrate_hik_camera.py`：Hikrobot 内参采集与标定。
- `solve_camera_rigid_to_optical.py`：ArUco + Mocap 求解相机刚体到光心外参。
- `verify_camera_rigid_to_optical.py`：相机外参重投影验证。
- `compute_static_camera_pose.py`：固定相机世界位姿计算。

### 动捕与自动标签

- `check_mocap_csv.py`：动捕 CSV 质量检查。
- `generate_mocap_labels.py`：Mocap 自动生成 YOLO Pose 标签。
- `batch_generate_mocap_labels.py`：多 session 批量生成标签。
- `visualize_auto_labels.py`：可视化检查自动标签。

### 数据集与训练

- `prepare_yolo_pose_dataset.py`：构建 YOLO Pose 数据集。
- `train_ultralytics_pose.py`：训练 Ultralytics YOLO Pose 模型。

### Replay / Tracking / Evaluation

- `smoke_replay_pipeline.py`：离线 replay smoke test。
- `run_live_pose.py`：实机实时推理入口。
- `run_kalman_ablation.py`：Kalman 消融实验。
- `evaluate_pose_results.py`：位姿结果评估。

### 管理与同步

- `manage_sessions.py`：session manifest 管理。
- `manage_datasets.py`：dataset manifest 管理。
- `manage_models.py`：model registry 管理。
- `register_capture_session.py`：注册采集 session。
- `process_single_session.py`：单 session 后处理流程。
- `sync_capture_to_host.py`：单 session 同步到主机。
- `sync_capture_batch_to_host.py`：批量同步到主机。

## 新增脚本规则

- 临时实验脚本：未来优先放 `scripts/dev/`。
- 数据同步脚本：未来优先放 `scripts/sync/`。
- 管理类脚本：未来优先放 `scripts/management/`。
- 正式主流程脚本：新增前先确认是否放根目录、分类目录或 `src/yolo6d_car/cli/`。
- 不要在根目录随意新增 one-off 脚本。
- 不要在整理阶段移动已有核心脚本；如果确需迁移，应先保留根目录 wrapper。
