# 注册采集 Session

`scripts\register_capture_session.py` 用来把一个采集目录转换成 session manifest 里的 `sessions:` 条目。

它适合在采集完成后使用，例如已经有：

```text
G:\YOLO6D_Car_Data\captures\<date>\<session_name>
```

脚本会读取目录路径和可选的 `capture_metadata.json`，自动填充标准字段。你可以先预览 YAML，也可以追加写入已有 manifest。

## 预览模式

```powershell
D:\Envs\yolo6d\python.exe scripts\register_capture_session.py ^
  --capture-root captures\2026-05-30\car_auto_capture_001 ^
  --paths-config configs\paths_local.yaml ^
  --session-id 2026-05-30_car_static_001 ^
  --camera-type d455 ^
  --motion-type static ^
  --speed-level static ^
  --split train ^
  --dry-run
```

这个命令只打印：

```yaml
sessions:
  - session_id: ...
```

不会修改文件。

## 追加到 Manifest

```powershell
D:\Envs\yolo6d\python.exe scripts\register_capture_session.py ^
  --capture-root captures\2026-05-30\car_auto_capture_001 ^
  --paths-config configs\paths_local.yaml ^
  --manifest configs\session_manifest_template.yaml ^
  --session-id 2026-05-30_car_static_001 ^
  --camera-type d455 ^
  --motion-type static ^
  --speed-level static ^
  --split train ^
  --append
```

正式写入前，脚本会：

- 检查 `session_id` 是否已经存在。
- 校验生成的条目是否合法。
- 自动创建带时间戳的 manifest 备份。

## 常用参数

```text
--lens 6mm
--intrinsics outputs\calibration\hik_6mm\camera_intrinsics_hik_6mm.yaml
--mocap-csv FZmotion_Data\raw_csv\<session_id>.csv
--camera-rigid hik_rigid
--object-rigid car_rigid
--occlusion none
--lighting normal
--background lab
```

如果 mocap CSV 还没准备好，可以先不填 `--mocap-csv`。脚本会把 mocap 标记为未启用，后续再补。

## 注册后检查

```powershell
D:\Envs\yolo6d\python.exe scripts\manage_sessions.py ^
  --manifest configs\session_manifest_template.yaml ^
  --paths-config configs\paths_local.yaml ^
  --action validate
```

等 FzMotion CSV 到位后，再补充：

- `mocap.csv_path`
- `camera_rigid`
- `object_rigid`
- `camera.intrinsics`

