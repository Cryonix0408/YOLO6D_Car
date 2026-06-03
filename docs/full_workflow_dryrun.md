# 完整流程 Dry-Run

`scripts\dryrun_full_workflow.py` 是实验前的离线检查脚本。它用来确认项目配置、路径和脚本入口是否连得上。

它不会连接真实相机，不会连接动捕，不会训练模型，也不会生成大数据。

## 它检查什么

- Python、依赖和导入是否正常。
- `configs\paths_local.yaml` 是否能解析。
- session manifest 结构是否正确。
- dataset manifest 结构是否正确。
- model registry 结构是否正确。
- replay、Kalman、训练、归档等命令是否能生成。
- 可选 smoke test 是否能跑通。

## 基础 dry-run

```powershell
D:\Envs\yolo6d\python.exe scripts\dryrun_full_workflow.py ^
  --paths-config configs\paths_local.yaml ^
  --session-manifest configs\session_manifest_template.yaml ^
  --dataset-manifest configs\dataset_manifest_template.yaml ^
  --model-registry configs\model_registry_template.yaml ^
  --model-id car_pose_12pts_v1_yolov8n_pose ^
  --run-name full_workflow_dryrun ^
  --output-dir results\workflow_dryruns\full_workflow_dryrun
```

输出会解析到：

```text
G:\YOLO6D_Car_Data\results\workflow_dryruns\full_workflow_dryrun
```

## 带 smoke test 的 dry-run

```powershell
D:\Envs\yolo6d\python.exe scripts\dryrun_full_workflow.py ^
  --paths-config configs\paths_local.yaml ^
  --session-manifest configs\session_manifest_template.yaml ^
  --dataset-manifest configs\dataset_manifest_template.yaml ^
  --model-registry configs\model_registry_template.yaml ^
  --model-id car_pose_12pts_v1_yolov8n_pose ^
  --run-name full_workflow_dryrun_smoke ^
  --execute-smoke-tests ^
  --execute-ablation-smoke ^
  --output-dir results\workflow_dryruns\full_workflow_dryrun_smoke
```

## 输出文件

```text
workflow_readiness_summary.json
workflow_readiness_summary.csv
workflow_dryrun_report.md
generated_commands.md
```

其中：

- `workflow_dryrun_report.md` 是给人看的报告。
- `generated_commands.md` 是后续步骤命令清单。

## 状态含义

`Ready`：

- 代码和配置入口存在，可以继续。

`Missing data expected`：

- 真实采集数据、CSV、标签或权重还不存在，这是实验前正常情况。

`Placeholder`：

- 接口已预留，但完整算法还没展开。

`Pending`：

- 需要真实硬件、真实数据或训练结果。

`Passed` / `Failed`：

- 可选 smoke 命令已经实际执行。

## 回到实验室后的下一步

1. 创建真实 `session_id`。
2. 确认相机内参。
3. 确认 mocap 刚体名。
4. 采集图像或视频。
5. 同步到主机。
6. 保存 FzMotion CSV。
7. 更新 session manifest。
8. 生成 mocap 标签。
9. 抽查标签 overlay。
10. 构建数据集。
11. 训练 YOLO Pose。
12. 运行 replay、Kalman 和评估。

