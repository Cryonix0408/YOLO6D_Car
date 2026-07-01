# Kalman 回放

Kalman 回放用于在离线数据上验证滤波效果。它不连接相机，只读取已有预测或 replay 数据。

## 适用场景

- 检查滤波器是否能稳定输出。
- 比较 raw pose 和 filtered pose。
- 调整 Kalman 参数。
- 在没有真实相机时做快速测试。

## 固定 Kalman 配置

```text
configs\kalman_fixed.yaml
```

示例：

```powershell
D:\Envs\yolo6d\python.exe scripts\smoke_replay_pipeline.py ^
  --config configs\local_smoke_replay.yaml ^
  --kalman-config configs\kalman_fixed.yaml ^
  --max-frames 100
```

## 可靠性自适应 Kalman 配置

```text
configs\kalman_reliability.yaml
```

示例：

```powershell
D:\Envs\yolo6d\python.exe scripts\smoke_replay_pipeline.py ^
  --config configs\local_smoke_replay.yaml ^
  --kalman-config configs\kalman_reliability.yaml ^
  --max-frames 100
```

## 输出内容

回放会输出每帧位姿，通常包括：

- 原始 PnP 平移和旋转
- 滤波后平移和旋转
- 置信度
- 重投影误差
- 是否被 gating 接受
- 是否使用预测保持

## 调参方向

如果滤波后仍然很抖：

- 增大测量噪声。
- 增强平滑。
- 检查关键点输入是否本身错误。

如果滤波明显滞后：

- 减小测量噪声。
- 增大过程噪声。
- 缩短 hold-last 时间。

如果遮挡后恢复慢：

- 调整 reliability gating。
- 检查检测置信度是否过低。

