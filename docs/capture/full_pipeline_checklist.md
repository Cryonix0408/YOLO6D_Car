# 完整流程检查表

本文档是项目总流程索引，用来确认从采集、标定、打标签、训练、推理到同步是否都能跑通。

主机项目路径：

```text
D:\Research\YOLO6D_Car
```

主机 Python：

```text
D:\Envs\yolo6d\python.exe
```

主机数据根目录：

```text
G:\YOLO6D_Car_Data
```

采集笔记本项目路径：

```text
D:\YOLO6D_Car
```

采集笔记本数据根目录：

```text
D:\CaptureData
```

## 总流程表

| 阶段 | 脚本入口 | 配置 | 输入 | 输出 | 是否需要硬件 | 主要用途 |
| --- | --- | --- | --- | --- | --- | --- |
| 路径管理 | `src/yolo6d_car/path_utils.py` | `configs/paths_laptop.yaml` / `configs/paths_local.yaml` | 本机路径配置 | 统一解析后的路径 | 否 | 区分笔记本和主机环境 |
| 海康相机预览 | `scripts/test_hikvision_camera.py` | 命令行参数 | 海康相机 | 实时窗口 | 是 | 调曝光、增益、视野和焦距 |
| 海康连续采集 | `scripts/collect_hikvision_sequence.py` | 命令行参数 | 海康相机 | `images/`、`camera_timestamps.csv`、`config.yaml` | 是 | fast-moving 连续帧采集 |
| 海康内参标定 | `scripts/calibrate_hik_camera.py` | `configs/calibration_hik_6mm.yaml` / `configs/calibration_hik_8mm.yaml` | 棋盘格图像 | `camera_intrinsics_*.yaml` | 采集阶段需要 | 每个镜头单独标定 |
| D455 采集 | `scripts/capture_object_samples.py` | `configs/object_capture*.yaml` | D455 图像 | 图片、深度、metadata | 是 | 旧静态数据流程 |
| 动捕 CSV 读取 | `src/yolo6d_car/mocap/csv_provider.py` | 项目 YAML 中的 `mocap.csv_path` | FzMotion CSV | 位姿查找器 | 否 | 打标签和 GT 对比 |
| 动捕 CSV 检查 | `scripts/check_mocap_csv.py` | 命令行参数 | FzMotion CSV | 质量报告 | 否 | 检查刚体、时间戳、丢帧 |
| Mocap 自动打标签 | `scripts/generate_mocap_labels.py` | `configs/fzmotion_fixed_camera*.yaml` | 图像、CSV、外参、模型点 | YOLO pose 标签和 overlay | 否 | 生成训练标签 |
| 批量打标签 | `scripts/batch_generate_mocap_labels.py` | 多 session manifest | 多组 session | 多组标签 | 否 | 批处理静态数据 |
| 数据集构建 | `scripts/prepare_yolo_pose_dataset.py` | 命令行参数 | auto_labels | `dataset.yaml` | 否 | 生成 Ultralytics 数据集 |
| YOLO Pose 训练 | `scripts/train_ultralytics_pose.py` | 命令行参数 | `dataset.yaml`、预训练模型 | `best.pt` | 建议 GPU | 训练关键点检测模型 |
| 实时推理 | `scripts/run_live_pose.py` | `configs/fzmotion_fixed_camera_live_v1*.yaml` | 相机、模型权重 | 实时 6DoF 位姿 | 是 | 在线演示 |
| Kalman 滤波 | `src/yolo6d_car/tracking/pose_kalman_filter.py` | `configs/kalman_fixed.yaml` / `configs/kalman_reliability.yaml` | 原始 PnP 位姿 | 平滑后的位姿 | 否 | fast-moving 稳定跟踪 |
| 结果评估 | `scripts/evaluate_pose_results.py` | 命令行参数 | 预测结果、GT | 误差指标和图表 | 否 | 对比 raw / filtered 结果 |
| 数据同步 | `scripts/sync_capture_to_host.py` / `scripts/sync_capture_batch_to_host.py` | 命令行参数 | 笔记本本地数据 | 主机共享盘数据 | 否 | 把采集数据传到主机 |

## 笔记本采集时推荐流程

1. 进入项目：

```powershell
cd D:\YOLO6D_Car
```

2. 先打开海康预览，调整曝光、增益、焦距和视野：

```powershell
python .\scripts\test_hikvision_camera.py --mvs-python-path "E:\MVS\Development\Samples\Python\MvImport" --frame-rate 60 --exposure-time-us 5000 --gain-db 6
```

3. 连续采集一组 session：

```powershell
python .\scripts\collect_hikvision_sequence.py --output-dir D:\CaptureData\2026-XX-XX_car_fast_lateral_001 --duration 30 --fps 60 --exposure-us 5000 --gain 6 --width 1440 --height 1080 --preview --preview-before-start
```

4. 检查采集质量：

```powershell
python .\scripts\check_capture_quality.py --capture-root D:\CaptureData\2026-XX-XX_car_fast_lateral_001 --output-dir D:\CaptureData\results\capture_quality\2026-XX-XX_car_fast_lateral_001 --plot
```

5. 回来后先扫描同步计划：

```powershell
python .\scripts\sync_capture_batch_to_host.py --local-root D:\CaptureData --host-root Z:\captures --plan-only
```

6. 正式同步：

```powershell
python .\scripts\sync_capture_batch_to_host.py --local-root D:\CaptureData --host-root Z:\captures --verify
```

## 主机训练时推荐流程

1. 进入项目：

```powershell
cd D:\Research\YOLO6D_Car
```

2. 检查项目和路径：

```powershell
D:\Envs\yolo6d\python.exe scripts\check_project_readiness.py --paths-config configs\paths_local.yaml
```

3. 检查动捕 CSV：

```powershell
D:\Envs\yolo6d\python.exe scripts\check_mocap_csv.py --csv-path FZmotion_Data\raw_csv\<session>.csv --paths-config configs\paths_local.yaml --camera-rigid <camera_rigid> --object-rigid <object_rigid> --output-dir results\mocap_quality\<session> --plot
```

4. 生成标签：

```powershell
D:\Envs\yolo6d\python.exe scripts\generate_mocap_labels.py --config configs\fzmotion_fixed_camera_current_rigids_gdrive.yaml --paths-config configs\paths_local.yaml --samples-dir captures\<date>\<session> --csv-path FZmotion_Data\raw_csv\<session>.csv --output-dir outputs\auto_labels\<session> --save-overlays
```

5. 生成数据集：

```powershell
D:\Envs\yolo6d\python.exe scripts\prepare_yolo_pose_dataset.py --paths-config configs\paths_local.yaml --auto-label-dir outputs\auto_labels\<session> --out-dir outputs\datasets\<dataset_name>
```

6. 训练：

```powershell
D:\Envs\yolo6d\python.exe scripts\train_ultralytics_pose.py --paths-config configs\paths_local.yaml --dataset outputs\datasets\<dataset_name>\dataset.yaml --model yolo11n-pose.pt --device 0 --project outputs\train_runs --name <run_name>
```

## 当前状态提醒

- D455 静态流程已经保留。
- 海康相机采集入口已经加入。
- 海康连续帧采集适合 fast-moving 数据。
- Kalman 滤波模块已经有基础框架。
- 真正要做高质量 fast-moving demo，还需要新的海康标定、连续帧数据、动捕对齐和滤波评估。

