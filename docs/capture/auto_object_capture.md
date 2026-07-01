# 自动采集小车图像

`scripts\capture_object_samples.py` 用于旧版 D455 / webcam 自动采集。它会根据画面变化、清晰度和时间间隔自动保存样本。

重要提醒：海康 MV-CS016-10UC 的连续帧采集请优先使用 `scripts\collect_hikvision_sequence.py`。`capture_object_samples.py` 中虽然能识别 `hikrobot` 配置名，但海康自动采集入口不是当前主线。

## 适用场景

- D455 静态或慢速采集。
- Webcam 调试。
- 无相机 dry-run 检查流程。
- 自动筛掉重复角度和模糊图像。

## 输出内容

典型输出目录：

```text
captures\<date>\<session_name>
├── images
├── previews
├── metadata
├── capture_index.csv
├── capture_metadata.json
└── capture_report.md
```

## 笔记本采集建议

如果在采集笔记本上运行，建议写到：

```text
D:\CaptureData\<session>
```

并使用：

```powershell
python .\scripts\capture_object_samples.py --config .\configs\object_capture_auto.yaml --paths-config .\configs\paths_laptop.yaml --output-dir D:\CaptureData\car_static_001
```

## 主机环境示例

如果在主机上运行：

```powershell
D:\Envs\yolo6d\python.exe scripts\capture_object_samples.py --config configs\object_capture_auto.yaml --paths-config configs\paths_local.yaml
```

## dry-run 检查

不连接真实相机，只跑自动采集逻辑：

```powershell
python .\scripts\capture_object_samples.py --config .\configs\object_capture_auto.yaml --paths-config .\configs\paths_laptop.yaml --dry-run --max-frames 20
```

## 自动保存逻辑

程序会检查：

- 是否距离上一张保存样本足够久。
- 当前图像是否足够清晰。
- 当前画面是否和上一张差异足够大。
- 小车位置、尺度或场景是否变化明显。

如果画面变化太小，程序会继续等待，不会重复保存几乎一样的图。

## 配置重点

`configs\object_capture_auto.yaml` 中常用字段：

- `capture.target_samples`：目标采集张数。
- `capture.min_time_between_samples_s`：两次保存之间最小时间间隔。
- `capture.blur_threshold`：清晰度阈值。
- `capture.min_position_change_px`：位置变化阈值。
- `capture.save_preview`：是否保存预览图。
- `output.root`：输出根目录。

## 和 mocap 的关系

该脚本只负责采集图片和 metadata，不直接生成 mocap 标签。后续需要：

1. 保存对应 FzMotion CSV。
2. 检查 CSV。
3. 用 `generate_mocap_labels.py` 打标签。
4. 用 `visualize_auto_labels.py` 抽查标签质量。

## 常见问题

输出目录已存在：

- 换一个 session 名。
- 或确认安全后加 `--overwrite`。

保存太慢：

- 降低 `min_time_between_samples_s`。
- 降低场景变化阈值。

保存太重复：

- 提高 `min_position_change_px`。
- 提高 `min_scene_change_score`。

海康相机不要用这个脚本作为主采集入口：

- 海康连续帧采集请用 `scripts\collect_hikvision_sequence.py`。

