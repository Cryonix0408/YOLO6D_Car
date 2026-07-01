# 单个 Session 处理流程

`scripts\process_single_session.py` 是一个轻量级编排脚本，用来按顺序处理一组采集数据。

它会把以下步骤串起来：

- session manifest 校验
- 采集质量检查
- mocap CSV 质量检查
- mocap 自动打标签
- 标签可视化
- 生成 replay 配置

它不会训练模型，也不会做 Kalman 消融。

## 先 dry-run

正式处理前先 dry-run。这个模式只检查 manifest、解析路径、写处理报告和命令记录，不真正跑数据处理。

```powershell
D:\Envs\yolo6d\python.exe scripts\process_single_session.py `
  --session-id 2026-05-30_car_static_001 `
  --manifest configs\session_manifest_template.yaml `
  --paths-config configs\paths_local.yaml `
  --output-dir results\session_processing\2026-05-30_car_static_001 `
  --dry-run
```

使用 `configs\paths_local.yaml` 时，输出目录会解析为：

```text
G:\YOLO6D_Car_Data\results\session_processing\2026-05-30_car_static_001
```

## 正式运行

当图像和 mocap CSV 都准备好后，去掉 `--dry-run`：

```powershell
D:\Envs\yolo6d\python.exe scripts\process_single_session.py `
  --session-id 2026-05-30_car_static_001 `
  --manifest configs\session_manifest_template.yaml `
  --paths-config configs\paths_local.yaml `
  --output-dir results\session_processing\2026-05-30_car_static_001
```

脚本会在第一处失败步骤停止，并把 stdout / stderr 写入 `process_summary.json`。

## 处理步骤

1. 调用 `scripts/manage_sessions.py --action validate` 校验 session manifest。
2. 调用 `scripts/check_capture_quality.py` 检查采集质量。
3. 调用 `scripts/check_mocap_csv.py` 检查 mocap CSV。
4. 调用 `scripts/generate_mocap_labels.py` 生成标签。
5. 调用 `scripts/visualize_auto_labels.py` 可视化标签。
6. 根据 session manifest 生成 replay 配置。

如果 `mocap.enabled=false`，和 mocap 相关的步骤会被跳过，并在报告里记录原因。

## 输出目录

```text
results\session_processing\<session_id>
├── process_summary.json
├── process_report.md
├── generated_commands.md
├── capture_quality
├── mocap_quality
└── label_visualization
```

## 注意事项

- 这个脚本不训练 YOLO Pose。
- 这个脚本不运行 Kalman ablation。
- 这个脚本不会修改原始图片、标签或 mocap CSV。
- 当前标签生成命令会使用 session 中的配置字段；真实实验时要确认它指向的是完整的项目 YAML，而不是单纯的内参 YAML。
- replay 配置只会在正式运行时写出。

## 常见问题

采集质量检查失败：

- 检查 `capture.root`、`images_dir` 和 `capture_index.csv`。

mocap CSV 检查失败：

- 检查 `mocap.csv_path`、`camera_rigid` 和 `object_rigid`。

标签生成失败：

- 检查传给 `generate_mocap_labels.py --config` 的配置是否完整。

标签可视化失败：

- 检查 `outputs.auto_labels` 中是否存在 `labels_yolo_pose/*.txt`。
- 检查图片文件名和标签文件名是否匹配。

