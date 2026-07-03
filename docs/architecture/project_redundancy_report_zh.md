# YOLO6D_Car 冗余与风险识别报告

生成日期：2026-07-01  
本报告只列候选，不执行删除、移动或重命名。

## 1. 明显冗余文件候选

| 文件/目录 | 冗余原因 | 当前是否被引用 | 风险 | 建议处理方式 |
| -- | -- | -- | -- | -- |
| `configs/calibration_hik_6mm.yaml` | 与 `configs/calibration/hik_6mm_calibration.yaml` 职责重复 | 未确认 | 中 | archive 或 keep temporarily |
| `configs/calibration_hik_8mm.yaml` | 与 `configs/calibration/hik_8mm_calibration.yaml` 职责重复 | 未确认 | 中 | archive 或 keep temporarily |
| `configs/object_capture.yaml` | 旧对象采集配置，已有新 `configs/capture/*` | 未确认 | 中 | archive |
| `configs/object_capture_auto.yaml` | 旧自动采集入口，和新 capture 配置有重叠 | 可能被文档引用 | 中 | need_manual_review |
| `configs/board_capture.yaml` | D455 旧标定板采集配置 | 可能仍用于 D455 | 高 | keep |
| `configs/*_gdrive.yaml` | 主机路径版本与 paths 机制重复 | 可能仍用于主机 | 中 | merge after path migration |
| `docs/archive/camera_phase1_acceptance_report_zh.md` | 阶段验收报告，不是长期主文档 | 否 | 低 | archive |
| `docs/archive/camera_phase1_sync_notes_zh.md` | 阶段同步说明 | 否 | 低 | archive |
| `docs/path_migration_audit.md` | 路径迁移过程审计 | 否 | 低 | archive |
| `docs/lab_commands_generated.md` | 自动生成命令快照 | 否 | 低 | archive/log |
| `docs/experiment_day_2026-05-30.md` | 单日实验记录 | 否 | 低 | docs/logs |
| `scripts/dryrun_full_workflow.py` | dry-run 原型脚本，非主流程 | 未确认 | 低 | scripts/dev candidate |
| `scripts/print_lab_commands.py` | 生成命令文档，偏辅助工具 | 未确认 | 低 | scripts/dev or tools |
| `scripts/test_color_correction.py` | 颜色校正实验脚本 | 否 | 低 | keep experimental |
| `tools/` 部分脚本 | PPT/讲义/报告一次性生成工具 | 未确认 | 低 | archive or tools/dev |

## 2. 可能重复的配置

| 重复类型 | 涉及文件 | 风险 | 建议 |
| -- | -- | -- | -- |
| Hik 内参标定配置双路径 | `configs/calibration_hik_6mm.yaml`, `configs/calibration/hik_6mm_calibration.yaml` | 改一个忘一个 | 以后只保留 `configs/calibration/`，旧路径保留 wrapper/文档兼容 |
| D455/Hik 固定相机配置混放 | `configs/fzmotion_*` 根目录文件 | 容易误用 D455/Hik 外参 | 后续移入 `configs/labeling/` 或 `configs/replay/` |
| 本地/G 盘配置并存 | `*_gdrive.yaml`, `paths_local.yaml`, `paths_laptop.yaml` | 路径双维护 | 优先统一到 paths-config |
| capture 配置新旧并存 | `configs/capture/*`, `configs/object_capture*.yaml` | 新手不知道用哪个 | README 标注推荐入口 |
| Kalman 配置在根目录 | `configs/kalman_*.yaml` | 根目录拥挤 | 可移入 `configs/tracking/` |
| smoke/replay 配置在根目录 | `configs/local_smoke_replay*.yaml` | 根目录拥挤 | 可移入 `configs/replay/` |

## 3. 可能重复的脚本

| 重复类型 | 涉及脚本 | 风险 | 建议 |
| -- | -- | -- | -- |
| 单 session 与批量同步 | `sync_capture_to_host.py`, `sync_capture_batch_to_host.py` | 使用入口不清 | 保留二者，但文档说明单个/批量场景 |
| Hik 连续采集与统一采集 | `collect_hikvision_sequence.py`, `capture_object_samples.py` | 后续数据结构不一致 | 以 `capture_object_samples.py` 为主，前者作为轻量调试工具 |
| 标定采集与 D455 board 采集 | `calibrate_hik_camera.py`, `capture_board_samples.py` | D455/Hik 流程容易混 | 文档明确 D455 legacy 与 Hik current |
| replay/pipeline/smoke | `run_pipeline.py`, `smoke_replay_pipeline.py`, `export_ultralytics_pose_to_replay.py` | 入口多 | 保留，按 smoke/export/live 三类文档化 |
| debug/prototype | `dryrun_full_workflow.py`, `print_lab_commands.py`, `test_color_correction.py` | 主流程目录噪声 | 后续归入 `scripts/dev/` |

## 4. 可能过时的文档

建议归档到 `docs/archive/` 或 `docs/logs/` 的候选：

| 文档 | 原因 | 建议 |
| -- | -- | -- |
| `camera_phase1_acceptance_report_zh.md` | 阶段验收结果 | `docs/archive/` |
| `camera_phase1_sync_notes_zh.md` | 阶段同步说明 | `docs/archive/` |
| `path_migration_audit.md` | 迁移审计历史 | `docs/archive/` |
| `lab_commands_generated.md` | 命令快照 | `docs/logs/` |
| `experiment_day_2026-05-30.md` | 单日记录 | `docs/logs/` |
| `build_first_then_execute_plan.md` | 阶段计划 | `docs/archive/` |

## 5. 当前最大冗余点 Top 10

1. `configs/` 根目录同时存在旧配置、新配置、路径配置、tracking/replay/session 配置。
2. Hik 标定配置存在根目录版和 `configs/calibration/` 版。
3. D455 与 Hik 的固定相机/mocap 配置命名不够显式。
4. `scripts/` 同时放主流程脚本、调试脚本、同步脚本和一次性工具。
5. 文档中核心流程和过程记录混放。
6. `*_gdrive.yaml` 与 `paths_local.yaml` 职责重叠。
7. `collect_hikvision_sequence.py` 与统一采集脚本边界不够清楚。
8. `tools/` 中部分讲义/PPT工具与项目主流程弱相关。
9. `outputs/`、`FZmotion_Data/` 等本地大数据目录存在于项目根目录，虽然被 ignore，但视觉上干扰结构。
10. 颜色校正实验模块刚加入，尚未决定是否进入主流程。

## 6. 当前最危险的结构问题 Top 5

1. 误用 D455/Hik 外参或内参，导致标签系统性飞。
2. 根目录旧配置和新配置并存，实验现场容易复制错命令。
3. 大数据路径在项目目录和 `D:\CaptureData` 之间混用。
4. 主机/笔记本路径差异如果绕过 `paths-config`，会造成脚本只能在一台机器跑。
5. 过早移动脚本会破坏已经验证过的旧命令。

## 7. .gitignore 检查建议

当前 `.gitignore` 已覆盖：`outputs/`, `captures/`, `results/`, `logs/`, `FZmotion_Data/`, `*.pt`, `*.onnx`, `*.mp4`, `*.avi`, `*.bag`, `*.npy`, `*.npz`, `!data/examples/`。

建议补充但本轮不修改：

```gitignore
CaptureData/
*.jpg
*.jpeg
*.png
*.bmp
*.tif
*.tiff
.pytest_cache/
```

注意：如果 `data/examples/` 里需要保留少量图片，补充 `*.png` 前要同时设置例外规则，避免误伤示例数据。
