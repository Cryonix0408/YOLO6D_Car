# 自定义小车模型说明

当前项目不再使用简单对称长方体，而是使用更贴近整车外轮廓的 12 点模型。

当前正式模型文件：

- [car_custom_keypoints_12_migrated_200xx_exact.json](../models/car_custom_keypoints_12_migrated_200xx_exact.json)

## 1. 为什么不用简单长方体

因为对这台小车来说，简单对称 cuboid 会带来几个问题：

- 轮子容易露在框外
- 车头 / 车尾外形不对称
- 视觉上“框到了”，但实际并不贴轮廓

## 2. 当前模型的来源

当前模型来自两部分：

- 真实动捕点
- 为外轮廓补充的虚拟点

这样做的目标是兼顾：

- 刚体稳定性
- 外轮廓可视化效果
- PnP 解算稳定性

## 3. 相关脚本

- 从 FzMotion CSV 构建模型：
  [build_custom_model_from_csv.py](../scripts/build_custom_model_from_csv.py)
- 刚体局部坐标迁移：
  [migrate_rigid_frame_from_csv.py](../scripts/migrate_rigid_frame_from_csv.py)

## 4. 修改模型时要同步的内容

一旦你改了模型 JSON，通常需要同步检查：

- 打标签配置中的 `model_json_path`
- 实时推理配置中的 `model_json_path`
- 训练数据是否需要重打标签

## 5. 接手建议

如果没有非常明确的需求，不建议随意改当前模型点顺序。  
因为模型点顺序会直接影响：

- 标签顺序
- 训练目标顺序
- PnP 的 2D/3D 对应关系
