# 实时推理说明

## 1. 目标

实时模式用于完成：

- 从 `D455` 实时取流
- 用训练好的 YOLO Pose 模型预测 12 个关键点
- 用 `PnP` 恢复小车 6DoF 位姿
- 在窗口中实时显示框、关键点、投影和姿态信息
- 可选输出实时 CSV 日志

## 2. 当前配置文件

当前实时推理配置模板：

- [fzmotion_fixed_camera_live_v1.yaml](../configs/fzmotion_fixed_camera_live_v1.yaml)

在实际使用前，请先确认其中的：

- `model_path`
- `object_model.model_json_path`
- `camera.*`
- `output.save_csv`

## 3. 推荐权重

当前推荐使用：

- [best.pt](../outputs/train_runs/uav_4m_20sessions_pose_v1/weights/best.pt)

如果实时配置还指向旧权重，请先手动修改 `model_path`。

## 4. 启动命令

```powershell
python .\scripts\run_pipeline.py --config .\configs\fzmotion_fixed_camera_live_v1.yaml
```

## 5. 运行时会输出什么

### 终端

默认会输出 JSON 行，包含：

- `frame_index`
- `timestamp_s`
- `prediction`
- `mocap_pose`
- `debug`

### 窗口

默认会显示：

- 关键点与轮廓投影
- 左上角 HUD
- 预测平移 / 姿态
- 推理模式（full / roi / fallback_full）

### CSV

如果配置了 `output.save_csv`，会额外写入日志文件。

## 6. 退出方式

- `Esc`
- 直接关闭窗口

## 7. 常见调试项

如果实时效果不理想，优先看：

- 训练权重是否正确
- ROI 参数是否过激进
- 时间滤波是否太强
- 模型关键点顺序是否与 `car_custom_keypoints_12_migrated_200xx_exact.json` 一致

