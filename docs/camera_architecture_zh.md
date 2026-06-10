# 相机统一架构说明

## 本机实际路径

- 项目目录：`D:\YOLO6D_Car`
- 采集数据根目录：`D:\CaptureData`
- 笔记本路径配置：`configs\paths_laptop.yaml`

文档中出现的 `D:\Research\YOLO6D_Car`、`D:\Envs\yolo6d` 或
`G:\YOLO6D_Car_Data` 属于主机示例路径，不是当前采集笔记本的实际路径。

## 设计目标

本次采用最小侵入式改造：保留原有 `D455Stream` 和 `HikvisionCamera`，
在其外部增加统一适配层。采集脚本只依赖统一接口，不再直接判断具体相机品牌。

## D455 与 Hikrobot 的区别

| 项目 | RealSense D455 | Hikrobot MV-CS016-10UC |
|---|---|---|
| 图像 | RGB | RGB |
| 深度 | 支持，可选择对齐到彩色图 | 不支持 |
| 快门 | 滚动快门 | 全局快门，更适合高速运动 |
| 镜头 | 集成镜头 | 可更换镜头，当前使用 6mm/8mm |
| SDK | `pyrealsense2` | 海康 MVS Python SDK |
| 关键风险 | 深度对齐与 RGB 分辨率 | 镜头内参混用、低光照、曝光过长 |

统一接口不会抹去两种相机的能力差异。D455 的 `depth` 可保存真实深度，
Hikrobot 的 `depth` 始终为 `None`；具体差异通过 `camera_type`、`lens`
和 `metadata` 继续保留。

统一帧结构 `CameraFrame` 包含：

- `rgb`：OpenCV BGR 图像
- `depth`：深度图；RGB-only 相机为 `None`
- `timestamp`：高精度时间戳
- `frame_id`：帧编号
- `camera_type`：`d455`、`hikrobot` 或 `webcam`
- `lens`：镜头标识，例如 `6mm`
- `intrinsics`：当前相机内参
- `metadata`：曝光、增益、像素格式等扩展信息

## 文件职责

| 文件 | 职责 |
|---|---|
| `src/yolo6d_car/camera/base_camera.py` | 定义 `CameraFrame` 和 `BaseCamera` |
| `src/yolo6d_car/camera/factory.py` | 根据配置创建统一相机后端 |
| `src/yolo6d_car/camera/d455.py` | 保留原有 D455 读取逻辑 |
| `src/yolo6d_car/camera/hikvision_camera.py` | 保留海康 MVS SDK 底层逻辑 |
| `src/yolo6d_car/camera/hikvision_stream.py` | 将海康底层类适配为统一接口 |
| `src/yolo6d_car/camera/webcam.py` | OpenCV 普通摄像头后端 |

## 调用流程

```text
capture_object_samples.py
        |
        v
camera.factory.create_camera(camera_config)
        |
        +-- D455CameraAdapter -> D455Stream
        +-- HikvisionStream   -> HikvisionCamera
        +-- WebcamCamera      -> cv2.VideoCapture
        |
        v
CameraFrame
```

`validate-config` 只检查配置结构，不会打开相机、枚举设备或要求 SDK 在线。

## 兼容性

- 原有 D455 类和命令继续保留。
- 原有海康测试与连续帧采集脚本继续使用底层 `HikvisionCamera`。
- 自动采集脚本通过 factory 支持 D455、Hikrobot 和 Webcam。
- `pipeline.py`、Kalman、evaluation 和 ablation 本轮不做大改。

## 重要约束

Hikrobot 的 6mm 与 8mm 镜头必须使用各自独立的内参文件。没有真实内参时，
适配器只允许完成图像采集和接口测试，不应使用近似内参进行高精度 PnP。

## Hikrobot 参数与补光建议

- 先固定帧率、曝光、增益和白平衡，再开始正式采集，避免同一 session 内参数漂移。
- `exposure_time_us` 越长画面越亮，但高速运动拖影越严重。
- `gain_db` 越高画面越亮，但噪声越明显，关键点精度会下降。
- `gamma` 只改变亮度映射，不能替代真实补光。
- 补光优先采用无频闪、高显色、覆盖均匀的灯具，避免只照亮局部车体。
- 6mm 与 8mm 镜头更换后必须重新标定内参；相机与刚体相对位置改变后必须重新标定外参。

## Fast-moving 为什么不能依赖长曝光

高速运动中，长曝光会让同一关键点在单帧内形成轨迹，导致 YOLO Pose 关键点位置
和 PnP 姿态同时产生系统误差。Fast-moving 数据应优先使用全局快门、短曝光和补光，
通过适度增益补足亮度，而不是单纯增加曝光时间。

## 回实验室如何选择配置

- D455 旧实验复现：使用 `configs/capture/d455_object_capture_auto.yaml`。
- Hikrobot 6mm 正式采集：使用 `configs/capture/hik_6mm_object_capture_auto.yaml`。
- Hikrobot 8mm 正式采集：必须先生成 8mm 内参，再使用对应采集配置。
- 仅检查接口：可使用 `configs/cameras/webcam.yaml`，但不用于高精度 PnP。
