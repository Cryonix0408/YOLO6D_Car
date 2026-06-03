# Mocap GT 位姿评估

本文档说明如何用 FzMotion 动捕结果作为 GT，对 YOLO6D 输出进行位姿误差评估。

## 为什么需要 mocap GT

只看画面 overlay，无法定量说明 6DoF 位姿准不准。用 mocap GT 可以得到：

- 平移误差
- 旋转误差
- 随时间变化的误差曲线
- 高速运动时误差是否变大
- Kalman 滤波是否真正改善结果

## 需要的数据

至少需要：

- 图像或连续帧采集数据
- 对应的 FzMotion CSV
- 相机外参
- 小车刚体到模型坐标系的变换
- YOLO6D / PnP 预测结果 CSV

## 基本流程

1. 检查 FzMotion CSV：

```powershell
D:\Envs\yolo6d\python.exe scripts\check_mocap_csv.py --csv-path FZmotion_Data\raw_csv\<session>.csv --paths-config configs\paths_local.yaml --camera-rigid <camera_rigid> --object-rigid <object_rigid> --output-dir results\mocap_quality\<session> --plot
```

2. 运行推理或回放，保存预测结果。

3. 对齐预测时间戳和 mocap 时间戳。

4. 计算误差。

## 误差定义

平移误差：

```text
e_t = || t_pred - t_gt ||
```

旋转误差：

```text
e_R = angle( R_gt^T R_pred )
```

如果用四元数，也可以通过相对四元数求旋转角。

## 注意事项

时间戳不对齐会让误差虚高：

- fast-moving 场景尤其敏感。
- 需要确认相机帧时间和 mocap 时间是否同一时间基准。

坐标系不一致会让结果完全错误：

- 检查 `T_camera_rigid_to_optical`。
- 检查 `T_object_rigid_to_model`。
- 检查相机刚体和小车刚体名称。

小车刚体重建后：

- 旧外参和旧 object model 可能不能直接复用。
- 需要重新验证标签 overlay。

## Demo 建议

如果时间紧，至少展示：

- raw PnP vs mocap GT 轨迹
- filtered pose vs mocap GT 轨迹
- 平移误差曲线
- 旋转误差曲线

