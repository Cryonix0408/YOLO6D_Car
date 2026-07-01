# 位姿结果评估

`scripts\evaluate_pose_results.py` 用于评估 YOLO6D / PnP / Kalman 输出的位姿结果。

## 目的

评估时主要回答这些问题：

- 原始 PnP 位姿是否稳定。
- Kalman 后是否降低抖动。
- fast-moving 场景下误差是否发散。
- 遮挡或模糊时是否出现大跳变。
- filtered pose 是否比 raw pose 更适合 demo。

## 输入

常见输入是回放或实时推理保存的 CSV，例如：

```text
outputs\replay_runs\<run>\pose_results.csv
```

如果有预处理后的 GT，也可以用于误差对比。

## 运行命令

```powershell
D:\Envs\yolo6d\python.exe scripts\evaluate_pose_results.py ^
  --input-csv outputs\replay_runs\latest\pose_results.csv ^
  --output-dir results\evaluation\latest ^
  --paths-config configs\paths_local.yaml ^
  --plot
```

## 输出

典型输出包括：

- 误差统计 JSON
- 评估报告 Markdown
- 轨迹图
- raw / filtered 对比图
- 平移误差和旋转误差曲线

## 重点指标

- 平移误差均值
- 平移误差最大值
- 旋转误差均值
- 旋转误差最大值
- 轨迹平滑程度
- 位姿突变次数
- 检测失败帧数量

## 解读建议

如果 raw 很抖但 filtered 稳：

- Kalman 有效果。

如果 filtered 稳但明显滞后：

- 滤波太强，需要调小平滑或增大过程噪声。

如果 raw 和 filtered 都跳：

- 可能是关键点检测或 PnP 输入本身错误，需要先检查标签、模型或内参。

如果评估结果看起来异常好：

- 检查是否测试集和训练集重叠。
- 检查 GT 是否和预测使用了同源数据。

