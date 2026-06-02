# 标定与对齐总说明

本项目里最关键的两个外参是：

1. `T_camera_rigid_to_optical`
2. `T_object_rigid_to_model`

在固定相机场景下，还可能使用：

3. `T_world_camera_optical`

## 1. 什么时候需要哪些量

### 情况 A：CSV 同时有相机刚体和小车刚体

需要：

- `T_camera_rigid_to_optical`
- `T_object_rigid_to_model`

### 情况 B：相机固定不动，只关心固定世界位姿

需要：

- `T_world_camera_optical`
- `T_object_rigid_to_model`

## 2. 推荐顺序

1. 先采标定板图像
2. 求 `T_camera_rigid_to_optical`
3. 确认小车模型点和 `T_object_rigid_to_model`
4. 再去批量打标签

## 3. 相关文档

- 相机刚体外参：
  [camera_rigid_calibration.md](./camera_rigid_calibration.md)
- 固定相机世界位姿：
  [fixed_camera_calibration.md](./fixed_camera_calibration.md)
- 小车模型：
  [custom_car_model.md](./custom_car_model.md)

## 4. 相关脚本

- [capture_board_samples.py](../scripts/capture_board_samples.py)
- [solve_camera_rigid_to_optical.py](../scripts/solve_camera_rigid_to_optical.py)
- [compute_static_camera_pose.py](../scripts/compute_static_camera_pose.py)
- [build_custom_model_from_csv.py](../scripts/build_custom_model_from_csv.py)

## 5. 使用建议

- 每次刚体重建后，都不要默认沿用上一版外参。
- 新外参不要一上来就批量重打所有标签，先抽一组验证。
- 一旦确认外参稳定，再批量重建标签和训练集。
