# docs/logs 实验日志说明

`docs/logs/` 用于存放单日实验记录、自动生成命令快照和实验过程记录。这里适合记录“当天做了什么、用了哪些命令、数据采到哪里、遇到什么问题、质量检查结论是什么”。

Phase A2 已完成 docs 分层整理：本轮只是把已经存在的日志类文档移动到本目录，并更新索引说明；没有删除任何历史文档。

## 当前日志文档

- [lab_commands_generated.md](lab_commands_generated.md)：实验室命令快照或自动生成命令记录。
- [experiment_day_2026-05-30.md](experiment_day_2026-05-30.md)：2026-05-30 单日实验过程记录。

## 使用建议

后续建议按日期和主题命名，例如 `docs/logs/2026-06-xx_lab_capture.md`。日志里优先记录 session 名称、相机参数、动捕 CSV、同步状态、标签质量和当天结论，避免把临时信息散落在 README 或主流程文档中。
