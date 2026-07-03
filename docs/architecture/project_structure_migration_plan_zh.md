# YOLO6D_Car 项目结构迁移计划

生成日期：2026-07-01  
本计划只提出迁移路线，本轮不执行移动、删除或重命名。

## Phase 总览

| Phase | 目标 | 涉及文件 | 风险 | 验证命令 | 是否建议现在执行 |
| -- | -- | -- | -- | -- | -- |
| Phase A | 文档索引和归档规划，不动代码 | `docs/`, `README.md` | 低 | `git status --short` | 是，但先只新增索引 |
| Phase B | 配置目录收口 | `configs/` | 中 | `capture_object_samples.py --validate-config` | 暂缓 |
| Phase C | 脚本目录收口 | `scripts/` | 高 | 全部常用命令 help/smoke | 暂缓 |
| Phase D | 源码模块收口 | `src/yolo6d_car/` | 高 | `python -m compileall src scripts` | 暂缓 |
| Phase E | 删除或归档候选 | docs/config/scripts legacy | 中高 | smoke + 实验命令回放 | 暂缓 |

## Phase A：只清理文档和配置说明，不动代码

目标：

1. 新增 `docs/index.md`。
2. 在 README 中只保留项目入口、当前推荐流程、核心文档链接。
3. 建立 `docs/archive/` 和 `docs/logs/` 的候选清单。
4. 标注哪些文档是“核心使用文档”，哪些是“过程记录”。

建议第一轮执行内容：

| 动作 | 文件 | 风险 | 备注 |
| -- | -- | -- | -- |
| 新增文档索引 | `docs/index.md` | 低 | 不影响旧命令 |
| 新增归档说明 | `docs/archive/README.md` | 低 | 先不移动文件 |
| README 简化 | `README.md` | 中 | 需避免删掉关键命令 |
| 标注实验记录 | `docs/logs/README.md` | 低 | 可选 |

验证命令：

```powershell
git status --short
```

是否建议现在执行：**是，但只新增索引，不马上移动旧文档。**

## Phase B：配置目录收口

目标：

1. `configs/paths/`：路径配置。
2. `configs/tracking/`：Kalman 配置。
3. `configs/replay/`：smoke/replay 配置。
4. `configs/labeling/`：mocap 标签/外参配置。
5. `configs/sessions/`：session manifest。
6. `configs/datasets/`：dataset manifest。
7. `configs/models/`：model registry。

风险：

1. 旧命令引用根目录配置会失效。
2. 实验现场复制旧命令会找不到配置。
3. 主机/笔记本同步时可能配置版本不一致。

兼容策略：

1. 第一阶段复制，不移动。
2. 文档优先使用新路径。
3. 旧路径保留至少一个实验周期。
4. 旧配置顶部加注释指向新配置。

验证命令：

```powershell
python .\scripts\capture_object_samples.py --config .\configs\capture\d455_object_capture_auto.yaml --paths-config .\configs\paths_laptop.yaml --validate-config
python .\scripts\capture_object_samples.py --config .\configs\capture\hik_6mm_object_capture_auto.yaml --paths-config .\configs\paths_laptop.yaml --validate-config
python .\scripts\smoke_replay_pipeline.py --config .\configs\local_smoke_replay.yaml --max-frames 3
```

是否建议现在执行：**否，等 Hik 6mm 标定采集稳定后再做。**

## Phase C：脚本目录收口

目标：

把脚本按功能移动到：

```text
scripts/capture/
scripts/calibration/
scripts/labeling/
scripts/dataset/
scripts/training/
scripts/replay/
scripts/tracking/
scripts/evaluation/
scripts/management/
scripts/sync/
scripts/dev/
```

兼容策略：

1. 根目录保留 wrapper 脚本。
2. wrapper 内部 import 新位置的 main。
3. 文档逐步切换到新命令。
4. 真实实验前不做大规模移动。

高风险脚本，短期不移动：

1. `generate_mocap_labels.py`
2. `capture_object_samples.py`
3. `solve_camera_rigid_to_optical.py`
4. `run_live_pose.py`
5. `train_ultralytics_pose.py`
6. `prepare_yolo_pose_dataset.py`

验证命令：

```powershell
python -m compileall src scripts
python .\scripts\generate_mocap_labels.py --help
python .\scripts\solve_camera_rigid_to_optical.py --help
python .\scripts\train_ultralytics_pose.py --help
```

是否建议现在执行：**否。**

## Phase D：源码模块收口

候选迁移：

| 当前模块 | 建议位置 | 是否急需 |
| -- | -- | -- |
| `dataset_manifest.py` | `management/` 或 `dataset/` | 否 |
| `model_registry.py` | `management/` | 否 |
| `session_manifest.py` | `management/` | 否 |
| `path_utils.py` | `utils/` | 否 |
| `config.py` | `utils/` 或保持根模块 | 否 |
| label generation 逻辑 | `labeling/` | 中期 |
| dataset 构建逻辑 | `dataset/` | 中期 |

建议：源码迁移必须最后做，因为 import 路径多，最容易破坏旧命令。

验证命令：

```powershell
python -m compileall src scripts
python .\scripts\smoke_replay_pipeline.py --config .\configs\local_smoke_replay.yaml --max-frames 3
python .\scripts\run_kalman_ablation.py --help
python .\scripts\evaluate_pose_results.py --help
```

是否建议现在执行：**否。**

## Phase E：删除或归档候选

本阶段只列候选，不删除：

| 候选 | 建议 | 前置条件 |
| -- | -- | -- |
| `docs/archive/camera_phase1_acceptance_report_zh.md` | archive | docs index 建好 |
| `docs/archive/camera_phase1_sync_notes_zh.md` | archive | 数据同步流程稳定 |
| `docs/path_migration_audit.md` | archive | paths-config 完全稳定 |
| `configs/calibration_hik_6mm.yaml` | archive | 所有命令改用 `configs/calibration/` |
| `configs/calibration_hik_8mm.yaml` | archive | 所有命令改用 `configs/calibration/` |
| `scripts/dryrun_full_workflow.py` | scripts/dev | 主流程文档稳定 |
| `scripts/print_lab_commands.py` | scripts/dev 或 tools | 实验命令文档稳定 |

是否建议现在执行：**否。**

## 推荐第一轮真正执行内容

建议下一条 Codex prompt 只做：

1. 新增 `docs/index.md`。
2. 新增 `docs/archive/README.md`，只列候选，不移动。
3. 新增 `docs/logs/README.md`，只列实验记录候选。
4. README 增加“当前推荐入口”段落，不删除历史内容。
5. 不移动脚本。
6. 不移动配置。
7. 不改核心代码。

## 必须保留不动的核心文件 Top 20

1. `scripts/capture_object_samples.py`
2. `scripts/generate_mocap_labels.py`
3. `scripts/solve_camera_rigid_to_optical.py`
4. `scripts/verify_camera_rigid_to_optical.py`
5. `scripts/calibrate_hik_camera.py`
6. `scripts/prepare_yolo_pose_dataset.py`
7. `scripts/train_ultralytics_pose.py`
8. `scripts/run_live_pose.py`
9. `scripts/smoke_replay_pipeline.py`
10. `scripts/run_kalman_ablation.py`
11. `scripts/evaluate_pose_results.py`
12. `src/yolo6d_car/config.py`
13. `src/yolo6d_car/path_utils.py`
14. `src/yolo6d_car/pipeline.py`
15. `src/yolo6d_car/camera/factory.py`
16. `src/yolo6d_car/camera/hikvision_camera.py`
17. `src/yolo6d_car/mocap/csv_provider.py`
18. `src/yolo6d_car/pose/pnp.py`
19. `src/yolo6d_car/tracking/pose_kalman_filter.py`
20. `models/car_custom_keypoints_12_migrated_200xx_exact.json`

## 下一步建议

短期先稳定 Hik 6mm 硬件链路和外参重标定，不做大规模结构调整。结构精简优先做文档索引和配置入口标注，等真实采集闭环稳定后再迁移目录。
