# 第一阶段相机架构整理验收报告

## 1. 验收结论

本轮第一阶段相机架构整理验收结果为：**条件通过**。

- 统一相机接口、相机工厂、Hikrobot 统一流适配器和 Webcam 后端均已存在。
- D455、Hikrobot 6mm、Hikrobot 8mm、Webcam 的相机配置与采集配置均已建立。
- `capture_object_samples.py` 已通过相机工厂使用统一接口，同时保留原有 D455 和 Hikrobot 底层代码。
- 笔记本路径配置已统一使用 `D:\CaptureData` 作为本地数据根目录。
- 使用项目可用的 Python 3.10 环境进行离线验证时，编译、replay smoke test 和三组采集配置校验均通过。
- 当前终端直接执行 `python` 时会进入缺少项目依赖的 Python 3.14 环境，因此用户要求的原始命令会失败。
- Hikrobot 8mm 内参文件尚未生成，8mm 配置只能完成结构校验，暂不能用于正式位姿估计。

本轮没有连接真实相机、没有采集数据、没有运行训练，也没有修改相机逻辑。

## 2. 本轮新增文件检查

### 2.1 相机模块

| 文件 | 是否存在 | 当前作用 |
|---|---|---|
| `src/yolo6d_car/camera/base_camera.py` | 是 | 定义统一的 `CameraFrame` 和 `BaseCamera` 接口 |
| `src/yolo6d_car/camera/factory.py` | 是 | 根据配置创建 D455、Hikrobot 或 Webcam 后端 |
| `src/yolo6d_car/camera/hikvision_stream.py` | 是 | 将原有 `HikvisionCamera` 适配为统一相机接口 |
| `src/yolo6d_car/camera/webcam.py` | 是 | 提供普通 Webcam/OpenCV 采集后端，用于接口测试 |

### 2.2 相机配置

| 文件 | 是否存在 | 当前作用 |
|---|---|---|
| `configs/cameras/d455.yaml` | 是 | D455 相机参数 |
| `configs/cameras/hik_6mm.yaml` | 是 | Hikrobot 6mm 镜头相机参数 |
| `configs/cameras/hik_8mm.yaml` | 是 | Hikrobot 8mm 镜头相机参数 |
| `configs/cameras/webcam.yaml` | 是 | Webcam 相机参数 |

### 2.3 采集配置

| 文件 | 是否存在 | 当前作用 |
|---|---|---|
| `configs/capture/d455_object_capture_auto.yaml` | 是 | D455 自动目标采集 |
| `configs/capture/hik_6mm_object_capture_auto.yaml` | 是 | Hikrobot 6mm 自动目标采集 |
| `configs/capture/hik_8mm_object_capture_auto.yaml` | 是 | Hikrobot 8mm 自动目标采集 |

### 2.4 标定配置

| 文件 | 是否存在 | 当前作用 |
|---|---|---|
| `configs/calibration/hik_6mm_calibration.yaml` | 是 | Hikrobot 6mm 内参标定 |
| `configs/calibration/hik_8mm_calibration.yaml` | 是 | Hikrobot 8mm 内参标定 |
| `configs/calibration/d455_rgb_calibration.yaml` | 是 | D455 RGB 内参标定 |

### 2.5 中文文档

| 文件 | 是否存在 | 当前作用 |
|---|---|---|
| `docs/camera_architecture_zh.md` | 是 | 说明统一相机架构、后端能力和限制 |
| `docs/camera_config_migration_zh.md` | 是 | 说明旧配置到新配置的迁移方式 |
| `README.md` 相机架构说明 | 是 | README 已包含相机架构入口及文档链接 |

## 3. 本轮修改文件

根据当前 Git 工作区状态，本阶段涉及的主要修改文件包括：

- `README.md`
- `scripts/capture_object_samples.py`
- `src/yolo6d_car/camera/__init__.py`

主要新增内容包括：

- `configs/cameras/`
- `configs/capture/`
- `configs/calibration/`
- `docs/camera_architecture_zh.md`
- `docs/camera_config_migration_zh.md`
- `src/yolo6d_car/camera/base_camera.py`
- `src/yolo6d_car/camera/factory.py`
- `src/yolo6d_car/camera/hikvision_stream.py`
- `src/yolo6d_car/camera/webcam.py`

本报告仅记录现状，没有修改上述相机实现和配置。

## 4. 当前相机架构

当前统一相机架构如下：

```text
capture_object_samples.py
        |
        v
camera.factory.create_camera()
        |
        +-- d455      -> D455CameraAdapter -> 原 D455Stream
        +-- hikrobot  -> HikvisionStream    -> 原 HikvisionCamera
        +-- webcam    -> WebcamCamera       -> OpenCV VideoCapture
```

统一接口由 `BaseCamera` 定义，单帧数据使用 `CameraFrame` 表示。采集脚本通过工厂创建相机，不再需要直接依赖具体品牌的底层实现。旧 D455 和 Hikrobot 后端仍被保留，属于最小侵入式适配。

## 5. 各相机当前状态

### 5.1 D455

状态：**离线配置验证通过，真实硬件待验证**。

- 已接入统一相机工厂。
- 原有 D455 代码保留。
- 配置中保留 RGB、Depth 和 `align_depth_to_color` 能力。
- `d455_object_capture_auto.yaml` 可通过离线配置校验。
- 尚未在本轮连接 D455 验证实际帧、深度对齐、时间戳和持续采集性能。

### 5.2 Hikrobot 6mm

状态：**离线配置验证通过，真实硬件待验证**。

- 已接入统一相机工厂。
- 6mm 内参文件存在：
  `D:\CaptureData\outputs\calibration\hik_6mm\camera_intrinsics_hik_6mm.yaml`
- 采集配置可通过离线校验。
- `white_balance` 字段已保留，但统一适配器尚未显式完整应用。
- 曝光、增益、Gamma、白平衡、实际帧率、时间戳稳定性仍需真实硬件验证。

### 5.3 Hikrobot 8mm

状态：**配置结构已建立，但暂不可正式使用**。

- 已建立独立的 8mm 相机、采集和标定配置。
- 文档已明确说明正式使用前必须生成：
  `camera_intrinsics_hik_8mm.yaml`
- 当前预期内参路径为：
  `D:\CaptureData\outputs\calibration\hik_8mm\camera_intrinsics_hik_8mm.yaml`
- 上述内参文件当前缺失。
- `configs/cameras/hik_8mm.yaml` 没有直接写明“当前尚未标定”，但配置引用、文档和校验警告能够反映该状态。

### 5.4 Webcam

状态：**接口和配置已建立，真实硬件待验证**。

- 可作为统一相机接口的轻量测试后端。
- 适合检查采集流程和接口兼容性。
- 不建议在未完成精确内参标定的情况下用于高精度 PnP/6DoF 位姿估计。

## 6. 路径配置检查

`configs/paths_laptop.yaml` 当前内容统一使用：

```text
project_root: D:\YOLO6D_Car
data_root: D:\CaptureData
fzmotion_root: D:\CaptureData\FZmotion_Data
captures_root: D:\CaptureData
outputs_root: D:\CaptureData\outputs
results_root: D:\CaptureData\results
logs_root: D:\CaptureData\logs
```

`models_root` 保留在项目目录 `D:\YOLO6D_Car\models`，属于合理安排。

结论：**笔记本本地数据路径已经统一到 `D:\CaptureData`。**

## 7. README 和文档路径检查

| 检查项 | 结果 | 说明 |
|---|---|---|
| 错误路径 `D:\Capture_Data` | 未发现 | 当前未扫描到该错误写法 |
| `D:\Envs\yolo6d\python.exe` 被写成笔记本唯一 Python | 未发现明确声明 | README 和旧文档中仍有多处该路径，主要属于主机/工作站示例，建议后续进一步标注适用机器 |
| `G:\YOLO6D_Car_Data` 被写成笔记本本地数据目录 | 未发现明确声明 | 该路径主要用于主机数据根目录和同步说明，部分旧文档仍可能让读者混淆 |
| README 笔记本实际路径说明 | 通过 | 已明确写出 `D:\YOLO6D_Car`、`D:\CaptureData` 和 `configs\paths_laptop.yaml` |

建议后续统一在旧文档命令前增加“采集笔记本”或“训练主机”标签，但本轮不修改文档。

## 8. Hikrobot 配置限制检查

| 检查项 | 结果 |
|---|---|
| Hik 6mm/8mm 配置包含 `white_balance` 字段 | 通过 |
| 文档说明统一适配器尚未显式完整应用 `white_balance` | 通过 |
| 当前 Hik 配置使用 `trigger_mode: off` | 通过 |
| 文档说明非 `off` trigger mode 尚未真实硬件验证 | 通过 |
| 8mm 正式使用前必须生成独立内参 | 通过 |
| 8mm 当前未标定状态在配置中明确直写 | 部分通过，当前通过文件缺失和文档说明体现 |

## 9. 离线验证命令结果

### 9.1 按用户要求直接使用 `python` 执行

| 命令 | 结果 | 原因 |
|---|---|---|
| `python -m compileall src scripts` | 失败 | 默认 Python 尝试写入 `.cpython-314.pyc`，并出现 `PermissionError` |
| `python scripts\smoke_replay_pipeline.py --config configs\local_smoke_replay.yaml --max-frames 3` | 失败 | `ModuleNotFoundError: No module named 'numpy'` |
| D455 `capture_object_samples.py --validate-config` | 失败 | `ModuleNotFoundError: No module named 'numpy'` |
| Hik 6mm `capture_object_samples.py --validate-config` | 失败 | `ModuleNotFoundError: No module named 'numpy'` |
| Hik 8mm `capture_object_samples.py --validate-config` | 失败 | `ModuleNotFoundError: No module named 'numpy'` |

结论：终端中的默认 `python` 当前不是项目可用环境，推测为 Python 3.14 且未安装项目依赖。此问题属于环境入口问题，不是相机架构代码失败。

### 9.2 使用当前可用 Python 3.10 项目环境复验

复验使用：

```text
C:\Users\25701\AppData\Local\Programs\Python\Python310\python.exe
PYTHONPATH=D:\YOLO6D_Car\src;C:\Users\25701\venvs\yolo6d\Lib\site-packages
```

| 验证项 | 结果 | 说明 |
|---|---|---|
| `compileall src scripts` | 通过 | 退出码 0 |
| smoke replay，3 帧 | 通过 | `status: ok`，完成 3 帧 |
| D455 配置校验 | 通过 | 无警告 |
| Hik 6mm 配置校验 | 通过 | 警告：`white_balance` 尚未显式应用 |
| Hik 8mm 配置校验 | 通过但有阻塞项 | 警告：8mm 内参文件缺失；`white_balance` 尚未显式应用 |

三组采集配置解析出的输出目录分别为：

```text
D:\CaptureData\2026-06-10\d455_car_auto_001
D:\CaptureData\2026-06-10\hik_6mm_car_auto_001
D:\CaptureData\2026-06-10\hik_8mm_car_auto_001
```

以上复验均为离线操作，没有打开真实相机。

## 10. 当前仍需真实硬件验证的内容

1. D455 RGB、Depth、深度和彩色对齐以及实际时间戳。
2. Hikrobot 6mm 和 8mm 的曝光、增益、Gamma、白平衡和实际帧率。
3. Hikrobot 连续采集的丢帧率、保存速度和时间戳稳定性。
4. Hikrobot `white_balance` 字段在统一适配器中的实际应用效果。
5. Hikrobot 非 `off` 硬触发模式。
6. Webcam 实际设备索引、分辨率和持续采集稳定性。
7. 新统一接口下各后端的启动、停止和异常恢复行为。

## 11. 当前已知 TODO

### 高优先级

1. 统一笔记本项目 Python 入口，使终端直接执行 `python` 时能够加载项目依赖。
2. 完成 Hikrobot 8mm 内参标定并生成 `camera_intrinsics_hik_8mm.yaml`。
3. 使用真实硬件分别验证 D455 和 Hikrobot 6mm 的采集流程。

### 中优先级

1. 确认是否需要在统一 Hikrobot 适配器中显式应用完整白平衡参数。
2. 验证非 `off` trigger mode，并记录支持范围。
3. 为不同镜头和相机建立真实采集验收记录。

### 低优先级

1. 清理或补充旧文档中“采集笔记本”和“训练主机”的路径标签。
2. 增加 Webcam 的离线/真实硬件 smoke test。
3. 后续在不破坏旧命令的前提下逐步迁移更多采集脚本到统一相机接口。

## 12. 下一步建议

1. 先修复或明确笔记本终端的 Python 启动方式，确保验收命令可直接复现。
2. 使用 Hikrobot 6mm 做一次短时真实采集验收，检查帧率、时间戳、曝光和保存结果。
3. 使用 D455 做一次短时真实采集验收，重点检查 Depth 和对齐功能。
4. 在使用 8mm 镜头前完成独立内参标定，不允许复用 6mm 内参。
5. 真实硬件验证通过后，再进入第二阶段的数据采集与模型流程验证。

