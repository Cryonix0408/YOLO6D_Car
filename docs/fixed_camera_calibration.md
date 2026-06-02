# 固定相机位姿说明

如果你的相机固定不动，并且不打算每次都依赖相机刚体轨迹，那么可以直接使用：

- `T_world_camera_optical`

它表示：

```text
世界坐标系 -> 相机光学坐标系
```

## 1. 什么时候用它

- 相机固定在场地里不动
- 相机刚体轨迹不稳定或不可用
- 希望把相机位姿当成常量

## 2. 使用方式

在 YAML 中填写：

- `mocap.T_world_camera_optical`

同时可以把：

- `camera_rigid_body`
- `T_camera_rigid_to_optical`

保留为参考值，或者根据你的使用方式关闭。

## 3. 相关脚本

- [compute_static_camera_pose.py](../scripts/compute_static_camera_pose.py)

这个脚本适合把多组静态样本求平均，得到一个较稳定的世界系相机位姿。

## 4. 注意

一旦相机位置、朝向或安装方式发生变化，就要重新计算。
