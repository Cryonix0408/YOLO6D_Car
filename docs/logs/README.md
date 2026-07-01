# docs/logs 实验日志说明

`docs/logs/` 建议用于存放单日实验记录、自动生成命令快照和实验过程记录。这里适合放“当天做了什么、用了哪些命令、数据采到哪里、遇到什么问题”的记录。

本轮安全精简只创建日志目录说明，不移动任何文件、不删除任何文件、不重命名任何文件。

## 建议未来放入 logs 的候选文档

- [docs/lab_commands_generated.md](../lab_commands_generated.md)：实验室命令快照或自动生成命令记录。
- [docs/experiment_day_2026-05-30.md](../experiment_day_2026-05-30.md)：单日实验过程记录。

后续如果要正式使用日志目录，建议按日期命名，例如 `docs/logs/2026-06-xx_lab_capture.md`，并在其中记录采集 session、相机参数、动捕 CSV、同步状态和质量检查结论。
