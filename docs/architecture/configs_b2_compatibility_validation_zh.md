# Configs B2 兼容验证报告

## 基本信息

- 验证日期：2026-07-02
- 项目路径：`D:\YOLO6D_Car`
- Git 分支：`codex/color-correction-prototype`
- 选用 Python：`C:\Users\25701\venvs\yolo6d\Scripts\python.exe`
- Python 版本：`Python 3.10.11`
- numpy：可导入，版本 `2.2.6`

## Python 环境选择

本轮没有使用默认 `python`，原因是默认解释器指向 `C:\Python314\python.exe`，该环境缺少 `numpy`，会在进入配置验证前报错：

```text
ModuleNotFoundError: No module named 'numpy'
```

本轮也检查了以下环境：

- `.\.venv\Scripts\python.exe`：不存在。
- `D:\Envs\yolo6d\python.exe`：不存在。
- `C:\Python314\python.exe`：存在，但不能导入 `numpy`。
- `C:\Users\25701\venvs\yolo6d\Scripts\python.exe`：存在，可导入 `numpy`，因此作为本轮验证环境。

## 旧 paths-config 验证结果

| 命令目标 | 配置 | paths-config | 结果 | 备注 |
| --- | --- | --- | --- | --- |
| D455 采集配置 validate | `configs\capture\d455_object_capture_auto.yaml` | `configs\paths_laptop.yaml` | 通过 | `status=ok`，不需要真实硬件。 |
| Hikrobot 6mm 采集配置 validate | `configs\capture\hik_6mm_object_capture_auto.yaml` | `configs\paths_laptop.yaml` | 通过 | `status=ok`；提示 `white_balance` 字段尚未由底层后端显式应用。 |
| Hikrobot 8mm 采集配置 validate | `configs\capture\hik_8mm_object_capture_auto.yaml` | `configs\paths_laptop.yaml` | 通过 | `status=ok`；提示 8mm 内参文件当前不存在。 |

旧路径结论：旧 `configs\paths_laptop.yaml` 仍可用，B2 复制迁移没有破坏旧采集配置 validate。

## 新 paths-config 验证结果

| 命令目标 | 配置 | paths-config | 结果 | 备注 |
| --- | --- | --- | --- | --- |
| D455 采集配置 validate | `configs\capture\d455_object_capture_auto.yaml` | `configs\paths\paths_laptop.yaml` | 通过 | `status=ok`，输出目录解析到 `D:\CaptureData\2026-07-02\d455_car_auto_001`。 |
| Hikrobot 6mm 采集配置 validate | `configs\capture\hik_6mm_object_capture_auto.yaml` | `configs\paths\paths_laptop.yaml` | 通过 | `status=ok`；提示 `white_balance` 字段尚未由底层后端显式应用。 |
| Hikrobot 8mm 采集配置 validate | `configs\capture\hik_8mm_object_capture_auto.yaml` | `configs\paths\paths_laptop.yaml` | 通过 | `status=ok`；提示 8mm 内参文件当前不存在。 |

新 paths-config 结论：新 `configs\paths\paths_laptop.yaml` 可被现有脚本读取，采集配置 validate 通过。

## Replay 配置验证结果

| 命令目标 | 配置 | 结果 | 备注 |
| --- | --- | --- | --- |
| 旧 replay smoke | `configs\local_smoke_replay.yaml` | 通过 | 输出 `status=ok`，`frames_requested=3`。 |
| 新 replay smoke | `configs\replay\local_smoke_replay.yaml` | 未通过 | 配置内容虽然与旧文件一致，但移动到 `configs\replay\` 后，相对路径 `models/car_custom_keypoints_12_migrated_200xx_exact.json` 被解析为 `D:\YOLO6D_Car\configs\models\...`，导致 `FileNotFoundError`。 |

新 replay warning：`configs\replay\local_smoke_replay.yaml` 目前不能直接作为旧 replay 配置的等价替代。原因不是复制内容不一致，而是现有加载逻辑会按配置文件所在目录解析相对路径。后续需要在 Phase B3/B4 中决定：要么改为项目根相对路径约定，要么在新 replay 配置中使用明确的相对/绝对路径策略。

## Tracking 配置验证情况

已查看：

```powershell
C:\Users\25701\venvs\yolo6d\Scripts\python.exe .\scripts\run_kalman_ablation.py --help
```

help 中只有 `--config`、`--paths-config`、`--run-name`、`--max-frames`、`--plot`、`--python` 等参数，没有单独的 `--kalman-config`、`--fixed-kalman-config`、`--reliability-kalman-config` 参数。

因此本轮没有强行运行 tracking 功能验证。当前结论是：`configs\tracking\kalman_fixed.yaml` 和 `configs\tracking\kalman_reliability.yaml` 已完成复制，但本轮仅确认了脚本 help，不做真实数据级验证。

## Manifest 模板 hash 一致性

| 旧路径 | 新路径 | Hash 是否一致 |
| --- | --- | --- |
| `configs\session_manifest_template.yaml` | `configs\sessions\session_manifest_template.yaml` | 一致：`80EC445CB8B2AF50C98EE9639D6DB176EBF4933BE5B3EB326CE7A050F03A720C` |
| `configs\dataset_manifest_template.yaml` | `configs\datasets\dataset_manifest_template.yaml` | 一致：`18C5837F62286AD9F52D4344D86F8F099F7E57BA0B36813413270E90A455CE11` |
| `configs\model_registry_template.yaml` | `configs\models\model_registry_template.yaml` | 一致：`FF12F58FCE4D164198F80E5693CC2623653985ACFE9F8585FA8AB436B8A8BF0D` |

## 当前 Warning

- 默认 `python` 仍指向 `C:\Python314\python.exe`，不适合作为本项目验证环境。
- `D:\Envs\yolo6d\python.exe` 不存在，文档或命令中如仍引用该路径，需要根据当前机器实际情况调整。
- Hikrobot 8mm 内参文件缺失：`D:\CaptureData\outputs\calibration\hik_8mm\camera_intrinsics_hik_8mm.yaml`。
- Hikrobot 配置中的 `white_balance` 字段已保留，但当前底层后端尚未显式完整应用。
- 新 replay 配置路径当前不完全兼容，原因是相对路径解析基准发生变化。

## 结论

B2 复制迁移没有破坏旧路径：旧 `paths_laptop.yaml` validate 和旧 `local_smoke_replay.yaml` smoke 均通过。

新 `configs\paths\paths_laptop.yaml` 已可用于采集配置 validate，说明新 paths 目录具备短期并存可用性。

新 `configs\replay\local_smoke_replay.yaml` 暂不等价可用，因为相对模型路径在新目录下解析错误。进入 Phase B3 前建议先记录该问题，不要删除旧 replay 配置。

## 后续建议

可以进入 Phase B3，但需要把 `configs\replay\local_smoke_replay.yaml` 标记为“复制完成但 replay smoke 未通过，待路径策略确认”。Phase B3 不建议删除旧配置，尤其不要删除 `configs\local_smoke_replay.yaml`。

## Phase B2.6 replay 新路径修复结果

### B2.5 失败原因

B2.5 中 `configs\replay\local_smoke_replay.yaml` smoke 未通过。原因是该配置从 `configs\local_smoke_replay.yaml` 原样复制到 `configs\replay\` 后，现有 `load_config()` 会以 `config_file.parents[1]` 作为路径解析根。

旧配置位于 `configs\local_smoke_replay.yaml` 时，解析根是项目根目录 `D:\YOLO6D_Car`；新配置位于 `configs\replay\local_smoke_replay.yaml` 时，解析根变为 `D:\YOLO6D_Car\configs`。因此原来的 `models/...` 会被解析为 `D:\YOLO6D_Car\configs\models\...`，导致模型 JSON 找不到。

### 本轮修改范围

本轮只修改了：

- `configs\replay\local_smoke_replay.yaml`
- `docs\architecture\configs_b2_compatibility_validation_zh.md`
- `docs\architecture\configs_migration_plan_zh.md`

旧 `configs\local_smoke_replay.yaml` 未修改。

### 新 replay 配置路径调整

`configs\replay\local_smoke_replay.yaml` 中调整了两个相对路径：

| 字段 | B2 复制时路径 | B2.6 修复后路径 | 说明 |
| --- | --- | --- | --- |
| `object_model.model_json_path` | `models/car_custom_keypoints_12_migrated_200xx_exact.json` | `../models/car_custom_keypoints_12_migrated_200xx_exact.json` | 从 `configs` 解析根回到项目根的 `models/`。 |
| `yolo6d.replay_json_path` | `data/examples/custom_model_12pt_predictions.json` | `../data/examples/custom_model_12pt_predictions.json` | 从 `configs` 解析根回到项目根的 `data/examples/`。 |

### B2.6 验证结果

| 验证项 | 结果 | 命令摘要 |
| --- | --- | --- |
| 旧 replay smoke | 通过 | `smoke_replay_pipeline.py --config .\configs\local_smoke_replay.yaml --max-frames 3` |
| 新 replay smoke | 通过 | `smoke_replay_pipeline.py --config .\configs\replay\local_smoke_replay.yaml --max-frames 3` |
| D455 旧 paths-config validate | 通过 | `capture_object_samples.py --paths-config .\configs\paths_laptop.yaml --validate-config` |
| D455 新 paths-config validate | 通过 | `capture_object_samples.py --paths-config .\configs\paths\paths_laptop.yaml --validate-config` |
| Hik 6mm 旧 paths-config validate | 通过 | 仍提示 `white_balance` 尚未由底层后端显式应用。 |
| Hik 6mm 新 paths-config validate | 通过 | 仍提示 `white_balance` 尚未由底层后端显式应用。 |
| Hik 8mm 旧 paths-config validate | 通过 | 仍提示 8mm 内参文件缺失。 |
| Hik 8mm 新 paths-config validate | 通过 | 仍提示 8mm 内参文件缺失。 |

### B2.6 结论

新旧 replay config 现在均可用。B2 复制兼容迁移没有破坏旧 replay；B2.6 修复后，新 replay 路径也可以通过 smoke test。

可以进入 Phase B3，但仍建议保留旧 `configs\local_smoke_replay.yaml`，不要急着删除旧路径。
