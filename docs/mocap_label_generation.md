# Mocap 自动打标签说明

## 1. 输入条件

在运行自动打标签前，需要准备好：

1. 一个小车采集目录，例如 `outputs/object_capture/<session>`
2. 对应的 FzMotion CSV
3. 正确的外参配置 YAML
4. 正确的小车模型 JSON

通常至少要有：

- `images/`
- `samples.csv`
- `intrinsics.json`

## 2. 基本命令

```powershell
python .\scripts\generate_mocap_labels.py `
  --config .\configs\fzmotion_fixed_camera_current_rigids.yaml `
  --samples-dir .\outputs\object_capture\<session_name> `
  --csv-path D:\YOLO6D_Car\FZmotion_Data\<session_name>.csv `
  --output-dir .\outputs\auto_labels\<session_name> `
  --save-overlays
```

## 3. 产物说明

输出目录里通常包括：

- `labels_yolo_pose/`：YOLO Pose 标签
- `overlays/`：用于抽查质量的可视化图
- `annotations.jsonl`：逐帧记录
- `images.txt`：图像路径清单
- `summary.json`：本次打标签统计

## 4. 什么时候要重新打标签

以下情况建议重打：

- 相机外参重标了
- 小车模型 JSON 改了
- `T_object_rigid_to_model` 改了
- 之前用错了 CSV 或 session

## 5. 抽查建议

每个 session 至少抽查：

- 近距离
- 中距离
- 远距离
- 正视角
- 侧视角

重点看：

- 轮廓是否包住车体
- 旋转方向是否正确
- 质心是否合理
- 有没有大面积飘移

## 6. 批量打标签

如果已经整理好 manifest，可以使用：

```powershell
python .\scripts\batch_generate_mocap_labels.py --manifest .\configs\uav_4m_20_sessions.yaml
```

## 7. 进阶参数

`generate_mocap_labels.py` 还支持这些临时覆盖参数：

- `--time-offset-s`
- `--dimensions-m`
- `--object-extents-m`
- `--object-translation-m`
- `--object-rpy-deg`

这些参数适合做快速排查，不适合长期替代正式 YAML 配置。
