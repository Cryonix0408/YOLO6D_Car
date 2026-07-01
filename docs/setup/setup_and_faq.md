# 环境部署与常见问题

## 1. 推荐环境

- 操作系统：Windows
- Shell：PowerShell
- Python：3.10
- 相机：Intel RealSense D455
- 动捕：FzMotion
- 深度学习框架：Ultralytics YOLO Pose

## 2. 安装依赖

基础依赖见：
[requirements.txt](../requirements.txt)

建议至少安装：

```powershell
python -m pip install -r .\requirements.txt
```

如果要连接 D455，还需要安装：

- `pyrealsense2`
- Intel RealSense SDK

当前机器上已验证可用的解释器是：

```powershell
C:\Users\25701\venvs\yolo6d\Scripts\python.exe
```

如果直接运行 `python` 发现缺 `numpy`、`yaml` 或 `ultralytics`，优先切到这个虚拟环境，或用上面的完整路径运行项目命令。

## 3. 最小健康检查

不连接 D455、不打开窗口时，可以先跑 replay smoke test：

```powershell
& C:\Users\25701\venvs\yolo6d\Scripts\python.exe .\scripts\smoke_replay_pipeline.py --max-frames 3
```

看到 `{"status": "ok", ...}` 说明配置加载、JSON replay、PnP、Mocap CSV 查询和 pipeline 主循环可以跑通。

## 4. 目录约定

- 动捕 CSV 默认放在：
  `D:\YOLO6D_Car\FZmotion_Data\`
- 采集结果默认放在：
  `D:\YOLO6D_Car\outputs\object_capture\` 或 `outputs\board_capture\`
- 自动标签默认放在：
  `D:\YOLO6D_Car\outputs\auto_labels\`
- 训练集默认放在：
  `D:\YOLO6D_Car\outputs\datasets\`
- 训练输出默认放在：
  `D:\YOLO6D_Car\outputs\train_runs\`

## 5. 常见问题

### 5.1 终端输入命令后看起来“卡住”

优先检查：

- 当前 Python 环境是否正确
- 是否有 `PowerShell profile` 执行策略问题
- CSV 文件是否被其他程序占用
- 当前脚本是不是正在扫描大 CSV

建议先试：

```powershell
python --version
```

如果 `python` 本身都不正常，再去执行项目命令。

### 5.2 `python` 命令不可用或环境不对

说明当前终端没有进入正确虚拟环境。  
优先使用你已经验证过能跑通项目的 Python 解释器。

### 5.3 `generate_mocap_labels.py` 很慢

可能原因：

- CSV 很大
- 磁盘比较慢
- `save-overlays` 会额外写很多 PNG
- 终端环境有问题，脚本根本没真正开始跑

判断脚本是否真的在运行，最直接的方法是看输出目录里是否开始出现：

- `labels_yolo_pose/`
- `overlays/`
- `summary.json`

### 5.4 标签质量不对

优先排查：

- `T_camera_rigid_to_optical`
- `T_world_camera_optical`
- `T_object_rigid_to_model`
- 当前使用的 `model_json_path`
- session 对应的 CSV 是否选对

### 5.5 D455 打不开

优先检查：

- 是否被 RealSense Viewer 占用
- 是否接在 USB 3.0
- 是否有其他程序正在读流
- depth 模式是否过高导致启动失败

### 5.6 实时推理结果不对

优先检查：

- `configs/fzmotion_fixed_camera_live_v1.yaml`
- `model_path` 是否指向最新 `best.pt`
- `object_model` 是否和训练时一致
- `ROI tracker` 和 `temporal filter` 是否符合当前场景

## 6. 建议操作习惯

- 一个 session 采完后，立刻打标签并抽查 overlay。
- 外参刚重标完时，不要立刻批量重打全部标签，先抽一组验证。
- 训练时默认使用 `best.pt`，不要把 `last.pt` 当最终模型。

