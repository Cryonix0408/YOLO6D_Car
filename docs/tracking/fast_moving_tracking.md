# Fast-Moving Object Tracking & Pose Estimation

## 1. 当前基础

项目已经有完整的 6DoF 闭环：

- D455 实时取流
- YOLO Pose 12 点关键点检测
- PnP 位姿恢复
- ROI 裁剪推理
- 时间滤波与短时丢帧保持
- Mocap 自动标签和离线真值对比

高速运动阶段不需要重做标定链路，建议先围绕“更快取流、更稳 ROI、更低滤波滞后、更清晰评估”推进。

## 2. 已加入的第一步

`UltralyticsLiveBackend` 的 ROI 跟踪现在支持 bbox 常速度预测：

- 连续检测到目标时，估计检测框的 `px/frame` 速度。
- 下一帧裁剪 ROI 前，将 ROI 按速度向前预测。
- 短时丢检时，在 `max_prediction_frames` 内继续用预测 ROI 搜索。
- 旧配置默认 `predict_motion: false`，现有实时配置行为不变。

高速运动配置文件：

- [fzmotion_fast_moving_live.yaml](../configs/fzmotion_fast_moving_live.yaml)

启动：

```powershell
python .\scripts\run_live_pose.py --config .\configs\fzmotion_fast_moving_live.yaml
```

如果 640x480@60 在当前 D455/USB 环境不可用，先降到 640x480@30 或 848x480@30；高速实验优先关闭 depth，减少相机和 USB 压力。

## 3. 推荐实验路线

### 阶段 A：实时基线对比

分别运行：

```powershell
python .\scripts\run_live_pose.py --config .\configs\fzmotion_fixed_camera_live_v1.yaml --save-csv .\outputs\baseline_live_pose_log.csv
python .\scripts\run_live_pose.py --config .\configs\fzmotion_fast_moving_live.yaml --save-csv .\outputs\fast_moving_live_pose_log.csv
```

对比：

- 平均 FPS / 低分位 FPS
- `prediction_source` 中 `full`、`roi`、`fallback_full` 占比
- 连续空预测帧数量
- 重投影误差均值和 95 分位
- 视觉 overlay 是否追得上高速横穿画面

### 阶段 B：采集高速专用数据

新增 session 时建议覆盖：

- 直线横穿、斜向接近、远近快速变化
- 低速 / 中速 / 高速三个速度段
- 亮灯 / 关灯、背景 A / B
- 运动模糊明显和不明显两种曝光条件

仍然沿用现有链路：

```powershell
python .\scripts\capture_object_samples.py --config .\configs\object_capture.yaml
python .\scripts\generate_mocap_labels.py --config .\configs\fzmotion_fixed_camera_current_rigids.yaml --samples-dir <samples> --csv-path <fz_csv> --output-dir <labels> --save-overlays
python .\scripts\prepare_yolo_pose_dataset.py --auto-label-dir <labels> --out-dir .\outputs\datasets\<fast_dataset_name>
```

### 阶段 C：模型和滤波升级

优先级建议：

1. 训练时加入高速 session 和运动模糊增强。
2. 加离线评估脚本，按速度分桶统计检测率和姿态误差。
3. 把当前简单时间滤波升级为常速度 / Kalman 位姿滤波。
4. 对 PnP 加入上一帧位姿先验和异常值门控。
5. 需要更高实时性时，再考虑 detector 跳帧 + tracker 插帧。

## 4. 判断是否成功

高速阶段建议用下面几个指标作为验收：

- 端到端实时 FPS 达到目标相机 FPS 的 80% 以上。
- 快速横穿时连续丢检不超过 2-3 帧。
- 有 mocap 对比时，平移误差和角度误差随速度升高不发散。
- ROI 模式占比提高，同时 `fallback_full` 占比下降。
- 画面中投影轮廓没有明显长期滞后。
