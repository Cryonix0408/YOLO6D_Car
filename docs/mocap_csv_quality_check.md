# Mocap CSV 质量检查

`scripts\check_mocap_csv.py` 用来检查 FzMotion 或通用 mocap CSV 是否可以用于自动打标签、回放和位姿对比。

## 支持的 CSV 格式

通用位姿 CSV：

```text
timestamp,rigid_body,tx,ty,tz,qx,qy,qz,qw
```

FzMotion CSV：

- 第一行通常以 `DataName` 开头。
- 刚体列由 FzMotion 多行表头描述。
- `LengthUnits` 会自动换算成米。

如果格式无法识别，脚本会输出明确错误，并打印表头预览，方便你确认是不是导出了错误文件。

## 只验证配置

```powershell
D:\Envs\yolo6d\python.exe scripts\check_mocap_csv.py ^
  --csv-path FZmotion_Data\raw_csv\2026-05-30_car_static_001.csv ^
  --paths-config configs\paths_local.yaml ^
  --camera-rigid d455_rigid ^
  --object-rigid car_rigid ^
  --output-dir results\mocap_quality\2026-05-30_car_static_001 ^
  --validate-config
```

这个模式会解析路径。如果 CSV 存在，也会预览格式，但不会做完整质量统计。

## 完整检查

```powershell
D:\Envs\yolo6d\python.exe scripts\check_mocap_csv.py ^
  --csv-path FZmotion_Data\raw_csv\2026-05-30_car_static_001.csv ^
  --paths-config configs\paths_local.yaml ^
  --camera-rigid d455_rigid ^
  --object-rigid car_rigid ^
  --output-dir results\mocap_quality\2026-05-30_car_static_001 ^
  --plot
```

使用 `--paths-config configs\paths_local.yaml` 时，相对路径会解析到 `G:\YOLO6D_Car_Data` 下。

## 输出文件

```text
mocap_summary.json
mocap_summary.csv
mocap_quality_report.md
rigid_body_list.txt
timestamp_distribution.png
position_trajectory_preview.png
```

如果没有安装 matplotlib，绘图会跳过，但基础检查仍然会运行。

## 检查内容

- 文件是否存在、文件大小
- 行数和帧数
- 时间戳范围和频率估计
- 空值、NaN、非法数字
- CSV 中包含哪些刚体
- 指定的相机刚体和目标刚体是否存在
- 每个刚体的有效帧数量
- 相邻帧位置跳变和旋转跳变
- CSV 读取耗时

## 结果解释

`PASS`：

- 需要的刚体都存在。
- 没发现严重质量问题。

`WARNING`：

- CSV 大体可用，但存在空值、NaN 或跳变异常。
- 需要人工判断是否影响当前 session。

`FAIL`：

- 缺少必须刚体。
- CSV 无法读取。
- CSV 格式无法识别。

如果相机刚体或小车刚体缺失，优先检查 FzMotion 导出时是否选择了正确刚体，以及 session manifest / 命令里的刚体名是否写对。

