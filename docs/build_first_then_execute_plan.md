# 先搭工程，再跑实验

本项目采用“先把工程入口搭好，再采集真实数据”的策略。不要把 placeholder 当成失败，它表示接口位置已经预留，等真实数据回来后继续补强。

## 阶段 0：环境和路径

目标：让 Python、CUDA、项目根目录和数据根目录稳定可控。

状态：基本完成。

检查命令：

```powershell
D:\Envs\yolo6d\python.exe scripts\check_project_readiness.py --paths-config configs\paths_local.yaml
```

## 阶段 1：相机标定

目标：分别标定海康 MV-CS016-10UC 的不同镜头，例如 6mm 和 8mm。

状态：棋盘格标定流程已搭建。

下一步：每个镜头采集 30 到 80 张姿态丰富的标定图，检查重投影误差和去畸变效果。

## 阶段 2：数据同步

目标：把采集笔记本上的 session 同步到主机 G 盘。

状态：已支持扫描、增量复制、覆盖选项、大小校验和日志。

下一步：用 `Z:\captures` 做真实 session 同步。

## 阶段 3：采集程序

目标：采集 D455 / 海康图像，并保存 metadata 和时间戳。

状态：D455 自动采集和海康连续帧采集入口都已存在。

下一步：海康 fast-moving 数据优先使用 `collect_hikvision_sequence.py`。

## 阶段 4：自动打标签

目标：结合图像、FzMotion CSV、相机外参、小车模型点，生成 YOLO Pose 标签。

状态：已搭建。

下一步：每组真实 session 先打标签并检查 overlay，再批量处理。

## 阶段 5：数据集构建

目标：把 auto labels 合并成 Ultralytics Pose 数据集。

状态：已搭建。

下一步：生成数据集后检查 `dataset.yaml`、图片数量、标签数量和 train/val 划分。

## 阶段 6：训练

目标：训练 YOLO Pose，并把训练结果保存在 G 盘。

状态：训练 wrapper 已搭建。

下一步：先短训 sanity run，再正式训练。

## 阶段 7：回放和实时推理

目标：回放验证 PnP 逻辑，实时入口连接相机和训练权重。

状态：replay smoke 可用，live 入口存在。

下一步：训练后用匹配的相机内参和模型权重运行 live。

## 阶段 8：固定 Kalman

目标：加入一个固定参数的 post-PnP 平滑基线。

状态：12D 匀速 Kalman 基线已接入 replay。

下一步：真实数据上比较 raw 和 filtered。

## 阶段 9：可靠性自适应 Kalman

目标：根据关键点可靠性、重投影误差和检测质量动态调整测量噪声。

状态：基础接口已预留。

下一步：先评估固定 Kalman，再设计动态可靠性信号。

## 阶段 10：评估和论文结果

目标：输出定量误差、轨迹图、消融图和实验结论。

状态：基础评估入口存在。

下一步：稳定预测日志和 mocap GT 格式后，完善离线评估报告。

