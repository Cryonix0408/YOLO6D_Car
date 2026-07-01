# Session Manifest 工作流

session manifest 用来统一记录每一组实验数据：图片在哪里、CSV 在哪里、相机是什么、镜头是什么、刚体名是什么、输出应该写到哪里。

它的价值是避免每次手写一长串命令，减少路径和刚体名写错。

## 典型字段

每个 session 至少应包含：

- `session_id`
- `capture.root`
- `capture.images_dir`
- `camera.type`
- `camera.lens`
- `camera.intrinsics`
- `mocap.enabled`
- `mocap.csv_path`
- `mocap.camera_rigid`
- `mocap.object_rigid`
- `outputs.auto_labels`
- `outputs.replay_config`
- `split`

## 路径解析

使用主机环境时：

```powershell
--paths-config configs\paths_local.yaml
```

相对路径会解析到：

```text
G:\YOLO6D_Car_Data
```

例如：

```text
captures\2026-05-30\session_001
```

会变成：

```text
G:\YOLO6D_Car_Data\captures\2026-05-30\session_001
```

## 注册新 session

先 dry-run：

```powershell
D:\Envs\yolo6d\python.exe scripts\register_capture_session.py ^
  --capture-root captures\2026-05-30\<session_id> ^
  --paths-config configs\paths_local.yaml ^
  --session-id <session_id> ^
  --camera-type hikrobot ^
  --lens 8mm ^
  --motion-type lateral ^
  --speed-level fast ^
  --split train ^
  --dry-run
```

确认无误后追加：

```powershell
D:\Envs\yolo6d\python.exe scripts\register_capture_session.py ^
  --capture-root captures\2026-05-30\<session_id> ^
  --paths-config configs\paths_local.yaml ^
  --manifest configs\session_manifest_template.yaml ^
  --session-id <session_id> ^
  --camera-type hikrobot ^
  --lens 8mm ^
  --motion-type lateral ^
  --speed-level fast ^
  --split train ^
  --append
```

## 校验 manifest

```powershell
D:\Envs\yolo6d\python.exe scripts\manage_sessions.py ^
  --manifest configs\session_manifest_template.yaml ^
  --paths-config configs\paths_local.yaml ^
  --action validate
```

## 单 session 处理

```powershell
D:\Envs\yolo6d\python.exe scripts\process_single_session.py ^
  --session-id <session_id> ^
  --manifest configs\session_manifest_template.yaml ^
  --paths-config configs\paths_local.yaml ^
  --output-dir results\session_processing\<session_id>
```

## 常见错误

路径存在于笔记本但主机找不到：

- 检查是否已经同步到 `G:\YOLO6D_Car_Data`。
- 检查 manifest 中是否还写着 `D:\CaptureData`。

mocap 刚体名不一致：

- 用 `check_mocap_csv.py` 看 CSV 里真实刚体名。
- 修改 manifest 里的 `camera_rigid` 和 `object_rigid`。

内参和镜头不匹配：

- 6mm 用 6mm 内参。
- 8mm 用 8mm 内参。

