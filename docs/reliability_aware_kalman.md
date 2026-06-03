# 可靠性自适应 Kalman

可靠性自适应 Kalman 的核心思想是：不是每一帧 YOLO/PnP 的测量都同样可信。检测质量好时更相信观测，检测质量差时更多相信预测。

## 为什么需要可靠性

fast-moving 场景中会出现：

- 运动模糊
- 部分遮挡
- 关键点误检
- 关键点顺序错乱
- PnP 解突变
- 短时检测失败

如果每一帧都直接把测量喂给 Kalman，错误观测会把状态带偏。

## 可靠性来源

可以综合以下信息：

- YOLO 检测置信度
- 关键点平均置信度
- 可见关键点数量
- PnP 重投影误差
- 位姿跳变大小
- bbox 是否合理
- 当前帧是否发生遮挡或模糊

## 基本策略

可靠性高：

- 降低测量噪声。
- 更相信当前观测。
- 快速修正预测。

可靠性低：

- 提高测量噪声。
- 减少错误观测影响。
- 必要时只预测，不更新。

观测明显离群：

- gating 拒绝该帧。
- 使用预测位姿或短时 hold-last。

## 配置文件

```text
configs\kalman_reliability.yaml
```

相关代码：

```text
src\yolo6d_car\tracking\reliability_estimator.py
src\yolo6d_car\tracking\pose_gating.py
src\yolo6d_car\tracking\pose_kalman_filter.py
```

## 评价方式

推荐比较：

- raw PnP
- fixed Kalman
- reliability-aware Kalman

重点看：

- 快速运动时是否更稳。
- 遮挡时是否少跳变。
- 恢复检测时是否能快速回到正确轨迹。
- 是否引入过大延迟。

## Demo 讲法

可以这样解释：

“我们不是简单地把每一帧检测结果平均掉，而是根据这一帧检测是否可靠，动态决定 Kalman 对观测的信任程度。这样在高速运动、遮挡和模糊时，系统不会被坏观测轻易带偏。”

