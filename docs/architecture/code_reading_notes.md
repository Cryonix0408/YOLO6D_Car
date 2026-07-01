# Code Reading Notes

这份文档记录读代码时发现的风险点和暂不重构的注意事项。

## 当前注意点

- `scripts/generate_mocap_labels.py` 的 `--config` 需要完整 ProjectConfig YAML，而不仅仅是 camera intrinsics YAML。真实 session manifest 里最好后续增加单独的 labeling config 字段，避免语义混淆。
- `src/yolo6d_car/tracking/pose_gating.py` 和 `state_machine.py` 是 placeholder，当前正式 tracking 状态主要在 `pose_kalman_filter.py` 中管理。
- `src/yolo6d_car/evaluation/compare_with_mocap.py` 是 placeholder；当前 GT 评估支持的是预处理后的 `gt_pose.csv`，不是原始 FzMotion CSV。
- README 中保留了一些历史命令示例，读新工作站流程时优先看 “New workstation setup: code on D drive, data on G drive” 以及 `docs/pipeline_gdrive_workflow.md`。

## 不在本轮修改的原因

本轮目标是注释和文档增强，不改变算法逻辑、不改 CLI 默认行为、不重构目录。上述风险点先记录，等真实实验数据回来后再根据实际阻塞程度决定是否改接口。
