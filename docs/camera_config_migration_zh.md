# 相机配置迁移说明

## 为什么保留旧配置

旧配置和旧命令已经支撑 D455 数据采集、标注与训练流程。本轮不删除旧文件，
而是在新目录中提供推荐模板，便于逐步迁移和回退。

## 推荐配置目录

```text
configs/
├── cameras/
│   ├── d455.yaml
│   ├── hik_6mm.yaml
│   ├── hik_8mm.yaml
│   └── webcam.yaml
├── capture/
│   ├── d455_object_capture_auto.yaml
│   ├── hik_6mm_object_capture_auto.yaml
│   └── hik_8mm_object_capture_auto.yaml
└── calibration/
    ├── d455_rgb_calibration.yaml
    ├── hik_6mm_calibration.yaml
    └── hik_8mm_calibration.yaml
```

## 当前笔记本路径

所有采集命令应传入：

```powershell
--paths-config .\configs\paths_laptop.yaml
```

该文件把大数据保存到 `D:\CaptureData`。主机路径配置不要直接用于采集笔记本。

## 离线验证

以下命令只验证配置，不连接真实相机：

```powershell
python .\scripts\capture_object_samples.py --config .\configs\capture\d455_object_capture_auto.yaml --paths-config .\configs\paths_laptop.yaml --validate-config

python .\scripts\capture_object_samples.py --config .\configs\capture\hik_6mm_object_capture_auto.yaml --paths-config .\configs\paths_laptop.yaml --validate-config

python .\scripts\capture_object_samples.py --config .\configs\capture\hik_8mm_object_capture_auto.yaml --paths-config .\configs\paths_laptop.yaml --validate-config
```

## 旧命令与推荐命令对照

| 用途 | 旧配置方式 | 推荐配置方式 |
|---|---|---|
| D455 自动采集 | `configs/object_capture_auto.yaml` 等历史配置 | `configs/capture/d455_object_capture_auto.yaml` |
| Hikrobot 6mm 自动采集 | 根目录中的临时 Hik 配置 | `configs/capture/hik_6mm_object_capture_auto.yaml` |
| Hikrobot 8mm 自动采集 | 根目录中的临时 Hik 配置 | `configs/capture/hik_8mm_object_capture_auto.yaml` |
| Hikrobot 6mm 内参标定 | 历史标定配置 | `configs/calibration/hik_6mm_calibration.yaml` |
| Hikrobot 8mm 内参标定 | 历史标定配置 | `configs/calibration/hik_8mm_calibration.yaml` |

旧配置不会删除，历史命令仍可复现。新配置用于后续新 session，便于明确相机、镜头
和标定文件之间的对应关系。

## 迁移规则

1. 旧命令仍可继续使用，不强制一次性迁移。
2. 新 session 必须记录 `camera.source`、`lens`、分辨率、曝光和增益。
3. Hikrobot 6mm 与 8mm 内参不可混用。
4. 标定配置只描述标定板和相机参数，采集配置只描述 session 与保存策略。
5. 没有完成投影验证的外参不得标记为最终配置。

## 当前仍需真实硬件验证

- Hikrobot 6mm/8mm 的实际曝光、增益、Gamma 和白平衡效果。
- Hikrobot 的 `white_balance` 与非 `off` 触发模式尚未在统一适配层显式应用。
- D455 深度与彩色图对齐后的实时性能。
- Hikrobot 8mm 内参文件当前是否已经生成。
- 自动采集在真实相机连续帧下的稳定性和保存速度。
