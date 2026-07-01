# 实验室执行计划

本文档是实验当天的执行包。目标不是一上来训练大模型，而是先跑通一条小而可靠的真实数据闭环。

## 前 10 分钟检查

硬件：

- [ ] 海康 MV-CS016-10UC 已连接。
- [ ] 8mm 镜头已装好、拧紧、清洁。
- [ ] 如果使用 6mm 镜头，确认对应镜头和内参。
- [ ] 小车可运行。
- [ ] 动捕球贴牢且可见。
- [ ] FzMotion 系统正常。
- [ ] 光照稳定。
- [ ] 电源、USB3.0、延长线、支架都固定好。
- [ ] 笔记本电量够，最好接电源。
- [ ] `Z:\` 主机共享盘可访问。

软件：

```powershell
cd D:\YOLO6D_Car
git status
Test-Path D:\CaptureData
Test-Path Z:\captures
```

相机预览：

```powershell
python .\scripts\test_hikvision_camera.py --mvs-python-path "E:\MVS\Development\Samples\Python\MvImport" --frame-rate 60 --exposure-time-us 5000 --gain-db 6
```

确认：

- [ ] 画面亮度能看清小车。
- [ ] 噪点不过分。
- [ ] 小车运动区域在画面内。
- [ ] 帧率接近设定值。
- [ ] FzMotion 中相机刚体名和小车刚体名确认。

## 是否需要先标定

以下情况需要重新标定内参：

- 换了镜头。
- 重新对焦。
- 镜头松动后重新安装。
- 分辨率改变。

海康 8mm 标定：

```powershell
python .\scripts\calibrate_hik_camera.py --config .\configs\calibration_hik_8mm.yaml --paths-config .\configs\paths_laptop.yaml --mode capture_and_calibrate
```

如果只做采集，不在笔记本上处理训练，可以先保证采集保存完整，标定结果后续同步到主机。

## 第一批 session 建议

最低可行组合：

| session | 运动 | 速度 | 用途 |
| --- | --- | --- | --- |
| `car_static_001` | 静止 | static | 检查时间戳和 PnP 基准 |
| `car_slow_lateral_001` | 横向移动 | slow | 容易成功的运动样本 |
| `car_fast_lateral_001` | 横向快速移动 | fast | Kalman 压力测试 |

效果更好的组合：

| session | 运动 | 速度 | 用途 |
| --- | --- | --- | --- |
| `car_static_001` | 静止 | static | 基准 |
| `car_slow_lateral_001` | 横向 | slow | 稳定运动 |
| `car_fast_lateral_001` | 横向 | fast | 快速运动 |
| `car_approach_001` | 靠近相机 | medium | 尺度变化 |
| `car_receding_001` | 远离相机 | medium | 远距离表现 |
| `car_rotation_001` | 转向/绕圈 | medium | yaw 和旋转稳定性 |
| `car_occlusion_001` | 局部遮挡 | slow | 鲁棒性 |

## 单个 session 操作

1. FzMotion 开始记录。
2. 采集脚本开始记录。
3. 小车按指定方式运动。
4. 停止采集脚本。
5. 停止 FzMotion 记录并导出 CSV。
6. 检查图片数量和 CSV 是否存在。
7. 记录异常情况。

采集命令示例：

```powershell
python .\scripts\collect_hikvision_sequence.py --output-dir D:\CaptureData\2026-XX-XX_car_fast_lateral_001 --duration 30 --fps 60 --exposure-us 5000 --gain 6 --width 1440 --height 1080 --preview --preview-before-start
```

CSV 建议保存到：

```text
D:\CaptureData\FZmotion_Data\2026-XX-XX_car_fast_lateral_001.csv
```

## 采集后检查

```powershell
dir D:\CaptureData\2026-XX-XX_car_fast_lateral_001
dir D:\CaptureData\2026-XX-XX_car_fast_lateral_001\images
```

采集质量检查：

```powershell
python .\scripts\check_capture_quality.py --capture-root D:\CaptureData\2026-XX-XX_car_fast_lateral_001 --output-dir D:\CaptureData\results\capture_quality\2026-XX-XX_car_fast_lateral_001 --plot
```

## 同步

先扫描：

```powershell
python .\scripts\sync_capture_batch_to_host.py --local-root D:\CaptureData --host-root Z:\captures --plan-only
```

正式同步：

```powershell
python .\scripts\sync_capture_batch_to_host.py --local-root D:\CaptureData --host-root Z:\captures --verify
```

## 实验当天不要做

- 不要在没看 overlay 前大规模训练。
- 不要混用 6mm 和 8mm 内参。
- 不要采集没有命名的 session。
- 不要只保存图像忘记保存 FzMotion CSV。
- 不要把大数据提交到 Git。
- 不要在相机参数没稳定时连续采很多组。

