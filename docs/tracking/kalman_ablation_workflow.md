# Kalman 消融实验流程

本文档用于比较未滤波位姿、固定 Kalman 滤波位姿、可靠性自适应 Kalman 滤波位姿之间的差异。

## 目的

fast-moving 场景中，YOLO 关键点和 PnP 位姿会抖动。Kalman 滤波的目标是：

- 降低位姿抖动。
- 在短时检测失败时保持连续输出。
- 减少明显离群点影响。
- 保持足够实时性，不能把运动滞后得太严重。

## 相关配置

固定参数版本：

```text
configs\kalman_fixed.yaml
```

可靠性自适应版本：

```text
configs\kalman_reliability.yaml
```

核心代码：

```text
src\yolo6d_car\tracking\pose_kalman_filter.py
src\yolo6d_car\tracking\reliability_estimator.py
src\yolo6d_car\tracking\pose_gating.py
```

## 运行消融

```powershell
D:\Envs\yolo6d\python.exe scripts\run_kalman_ablation.py ^
  --input-csv outputs\replay_runs\<run>\pose_results.csv ^
  --output-dir results\kalman_ablation\<run> ^
  --paths-config configs\paths_local.yaml
```

如果脚本要求指定配置，则分别运行：

```powershell
D:\Envs\yolo6d\python.exe scripts\smoke_replay_pipeline.py ^
  --config configs\local_smoke_replay.yaml ^
  --kalman-config configs\kalman_fixed.yaml ^
  --max-frames 100
```

```powershell
D:\Envs\yolo6d\python.exe scripts\smoke_replay_pipeline.py ^
  --config configs\local_smoke_replay.yaml ^
  --kalman-config configs\kalman_reliability.yaml ^
  --max-frames 100
```

## 需要观察的指标

- 平移误差是否下降。
- 旋转误差是否下降。
- 轨迹是否更平滑。
- 快速转弯时是否明显滞后。
- 检测失败后是否能合理保持。
- 恢复检测后是否能快速重新收敛。

## Demo 建议

展示时建议放三条轨迹：

- raw PnP
- fixed Kalman
- reliability-aware Kalman

如果自适应版本能在低置信度、遮挡、运动模糊时更稳，就重点讲这一版。

