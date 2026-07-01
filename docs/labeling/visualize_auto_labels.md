# 自动标签可视化检查

`scripts\visualize_auto_labels.py` 用来检查 `scripts\generate_mocap_labels.py` 生成的标签质量。它只读取图片和标签，不会修改原始标签或图像。

## 什么时候使用

在构建数据集或训练前，建议先用它抽查标签，确认：

- 12 个小车关键点是否投影到正确位置。
- 关键点编号顺序是否符合模型定义。
- 2D bbox 是否合理。
- 标签文件和图片文件是否一一匹配。
- 如果 `annotations.jsonl` 中有投影点，能额外画出 3D 外轮廓线。

## 输入目录

典型自动标签目录：

```text
G:\YOLO6D_Car_Data\outputs\auto_labels\<session_id>
├── labels_yolo_pose
│   ├── sample_000001.txt
│   └── ...
├── annotations.jsonl
├── summary.json
└── images.txt
```

典型采集图片目录：

```text
G:\YOLO6D_Car_Data\captures\<date>\<session_id>\images
```

YOLO pose 标签格式：

```text
class_id cx cy w h kp1_x kp1_y kp1_v ... kp12_x kp12_y kp12_v
```

其中 bbox 和关键点坐标都是归一化坐标。脚本显示时会自动转换为像素坐标。

## 只验证配置

这个模式只解析路径和导入 OpenCV，不扫描图片，也不写输出：

```powershell
D:\Envs\yolo6d\python.exe scripts\visualize_auto_labels.py `
  --labels-root outputs\auto_labels\2026-05-30_car_static_001 `
  --images-root captures\2026-05-30\2026-05-30_car_static_001\images `
  --paths-config configs\paths_local.yaml `
  --output-dir results\label_visualization\2026-05-30_car_static_001 `
  --max-samples 100 `
  --validate-config
```

## 正式可视化

```powershell
D:\Envs\yolo6d\python.exe scripts\visualize_auto_labels.py `
  --labels-root outputs\auto_labels\2026-05-30_car_static_001 `
  --images-root captures\2026-05-30\2026-05-30_car_static_001\images `
  --paths-config configs\paths_local.yaml `
  --output-dir results\label_visualization\2026-05-30_car_static_001 `
  --max-samples 100
```

使用 `configs\paths_local.yaml` 时，`outputs`、`captures`、`results` 会解析到 `G:\YOLO6D_Car_Data` 下。

## 输出目录

```text
G:\YOLO6D_Car_Data\results\label_visualization\<session_id>
├── overlays
│   ├── sample_000001_overlay.png
│   └── ...
├── contact_sheet.png
├── label_visualization_report.md
└── label_stats.json
```

## 报告会检查什么

- 标签数量
- 图片数量
- 图片和标签匹配数量
- 有标签但缺图
- 有图但缺标签
- 无效标签文件
- NaN / Inf 关键点
- 可见关键点是否超出图像范围
- 2D bbox 是否无效
- 每张图可见关键点数量统计

结果含义：

- `PASS`：抽查样本结构正常。
- `WARNING`：脚本跑完，但有部分文件需要人工看。
- `FAIL`：没有匹配样本，或者匹配标签全部无效。

## 常见问题

没有匹配样本：

- 图片文件名和标签文件名 stem 不一致。

关键点跑出画面：

- 检查相机内参。
- 检查 mocap 刚体名称。
- 检查图像和动捕时间戳是否对齐。

bbox 无效：

- 检查物体关键点投影。
- 检查标签归一化逻辑。

3D 线框没画出来：

- `annotations.jsonl` 可能没有 `projected_keypoints_px`。

输出到了 G 盘：

- 使用 `--paths-config configs\paths_local.yaml` 且输出路径写相对路径时，这是正常的。

