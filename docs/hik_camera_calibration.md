# 海康工业相机标定说明

本项目使用海康 MV-CS016-10UC 工业相机。你目前主要涉及 6mm 和 8mm 镜头。

每次更换镜头、改变焦距、重新对焦、明显改变安装方式后，都应该重新标定内参。6mm 和 8mm 的内参不能混用。

## 输出目录

主机训练环境下，标定结果建议保存到：

```text
G:\YOLO6D_Car_Data\outputs\calibration
```

6mm 镜头输出示例：

```text
G:\YOLO6D_Car_Data\outputs\calibration\hik_6mm
├── raw_images
├── debug_corners
├── samples
├── undistort_check
├── camera_intrinsics_hik_6mm.yaml
├── calibration_report_hik_6mm.md
└── calibration_summary.json
```

8mm 镜头输出示例：

```text
G:\YOLO6D_Car_Data\outputs\calibration\hik_8mm
├── raw_images
├── debug_corners
├── samples
├── undistort_check
├── camera_intrinsics_hik_8mm.yaml
├── calibration_report_hik_8mm.md
└── calibration_summary.json
```

如果同名 session 已存在且没有加 `--overwrite`，程序会自动生成带时间戳的新目录。

## 标定板配置

当前默认使用棋盘格：

```yaml
calibration_board:
  type: "chessboard"
  pattern_cols: 9
  pattern_rows: 6
  square_size_mm: 25.0
```

注意：`pattern_cols` 和 `pattern_rows` 是“内角点数量”，不是打印方格数量。

## 标定采集建议

标定板要平整、硬、不要弯。镜头必须拧紧，采集过程中不要重新对焦。

建议覆盖这些姿态：

- 画面中心
- 左上
- 右上
- 左下
- 右下
- 近距离
- 远距离
- 向前/向后倾斜
- 顺时针/逆时针旋转

推荐有效样本数：30 到 80 张。

## 运行 6mm 标定

只验证配置，不打开相机：

```powershell
D:\Envs\yolo6d\python.exe scripts\calibrate_hik_camera.py --config configs\calibration_hik_6mm.yaml --paths-config configs\paths_local.yaml --mode validate_config
```

采集并自动标定：

```powershell
D:\Envs\yolo6d\python.exe scripts\calibrate_hik_camera.py --config configs\calibration_hik_6mm.yaml --paths-config configs\paths_local.yaml --mode capture_and_calibrate
```

只采集：

```powershell
D:\Envs\yolo6d\python.exe scripts\calibrate_hik_camera.py --config configs\calibration_hik_6mm.yaml --paths-config configs\paths_local.yaml --mode capture
```

从已有样本重新标定：

```powershell
D:\Envs\yolo6d\python.exe scripts\calibrate_hik_camera.py --config configs\calibration_hik_6mm.yaml --paths-config configs\paths_local.yaml --mode calibrate
```

## 运行 8mm 标定

只验证配置：

```powershell
D:\Envs\yolo6d\python.exe scripts\calibrate_hik_camera.py --config configs\calibration_hik_8mm.yaml --paths-config configs\paths_local.yaml --mode validate_config
```

采集并自动标定：

```powershell
D:\Envs\yolo6d\python.exe scripts\calibrate_hik_camera.py --config configs\calibration_hik_8mm.yaml --paths-config configs\paths_local.yaml --mode capture_and_calibrate
```

## 自动采样逻辑

标定程序会自动判断当前帧是否值得保存。你只需要移动标定板，程序会筛掉重复或质量差的图像。

每帧会检查：

- 是否完整检测到棋盘格。
- 清晰度是否高于 `capture.blur_threshold`。
- 角点覆盖范围是否足够。
- 距离上一张保存图是否间隔足够久。
- 当前视角是否和之前样本差异足够大。

如果当前视角太像之前保存过的样本，会显示：

```text
too similar to previous samples
```

达到 `min_samples` 后，程序会进入自动标定倒计时。如果你继续移动标定板并采到有效新样本，倒计时会后移。达到 `max_samples` 后自动停止采集并开始标定。

## 采集窗口按键

- `q` 或 `Esc`：退出
- `s`：强制保存下一张检测到棋盘格的图
- `c`：达到最小样本数后停止采集并标定
- `r`：重置当前运行中的样本差异记忆

## 如何判断标定质量

打开报告：

```powershell
notepad G:\YOLO6D_Car_Data\outputs\calibration\hik_8mm\calibration_report_hik_8mm.md
```

重投影误差越小越好。如果 RMS 或 mean error 明显偏高，优先检查：

- 棋盘格尺寸是否填错。
- `pattern_cols` / `pattern_rows` 是否填的是内角点。
- 图像是否模糊。
- 样本姿态是否太单一。
- 镜头是否松动或采集中重新对焦。
- 6mm 和 8mm 样本是否混在一起。

同时检查：

```text
debug_corners
undistort_check
```

## 在 PnP / 实时推理中使用内参

使用哪个镜头，就用哪个镜头对应的内参文件：

```text
G:\YOLO6D_Car_Data\outputs\calibration\hik_6mm\camera_intrinsics_hik_6mm.yaml
G:\YOLO6D_Car_Data\outputs\calibration\hik_8mm\camera_intrinsics_hik_8mm.yaml
```

不要把原始标定图片和生成输出提交到 Git。`outputs/` 应该由 `.gitignore` 忽略。

## 常见问题

相机打不开：

- 检查 USB3.0 连接。
- 关闭 MVS Viewer 或其他占用相机的软件。
- 确认海康 MVS SDK 已安装。
- 确认 Python 能找到 MVS SDK 的 `MvCameraControl_class.py`。

检测不到棋盘格：

- 确认棋盘格内角点数量。
- 增强光照。
- 保证整个棋盘格在画面内。
- 减少运动模糊。

图像被判定为模糊：

- 提高光照。
- 略微增加曝光。
- 稳定标定板。
- 重新调焦。

覆盖范围太小：

- 把标定板移近。
- 让棋盘格覆盖画面更多区域。

视角太相似：

- 把板移动到画面不同位置。
- 改变距离。
- 增加倾斜和旋转。

