# scripts/dev 目录说明

`scripts/dev/` 用于未来放临时实验脚本、debug 脚本、prototype 脚本和一次性测试脚本。

适合放在这里的脚本类型包括：

- dry-run 工具。
- 可视化调试工具。
- color correction 等离线实验脚本。
- 临时数据检查脚本。
- 不属于正式 pipeline 的 one-off 工具。

不要把正式主流程脚本直接放进 `dev/`。如果某个 prototype 稳定下来，应考虑迁移为正式脚本，或整理为 `src/yolo6d_car/` 下的可复用模块。

本轮 Phase C2 只创建目录说明，不移动任何现有脚本。
