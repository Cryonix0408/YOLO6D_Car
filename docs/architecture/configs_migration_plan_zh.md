# configs 配置目录收口与兼容迁移方案

本文档用于 Phase B1：梳理 `configs/` 当前状态，设计后续工程化配置目录结构，并给出安全、兼容、可回退的迁移方案。

本轮只写方案，不移动、不复制、不删除、不重命名任何 YAML / JSON 配置文件，也不修改现有配置内容。

## 1. 当前 configs 总览

| 当前文件 | 当前用途 | 所属模块 | 是否主流程 | 是否旧配置 | 是否建议迁移 | 推荐目标路径 | 风险 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `configs/paths_local.yaml` | 主机路径配置 | paths | 是 | 否 | 是 | `configs/paths/paths_local.yaml` | 中：主机训练、同步、评估命令依赖 |
| `configs/paths_laptop.yaml` | 采集笔记本路径配置 | paths | 是 | 否 | 是 | `configs/paths/paths_laptop.yaml` | 中：笔记本采集和同步命令依赖 |
| `configs/cameras/d455.yaml` | D455 相机硬件配置 | cameras | 是 | 否 | 已在目标目录 | `configs/cameras/d455.yaml` | 低 |
| `configs/cameras/hik_6mm.yaml` | Hikrobot 6mm 相机配置 | cameras | 是 | 否 | 已在目标目录 | `configs/cameras/hik_6mm.yaml` | 中：6mm 内参、曝光、白平衡易混 |
| `configs/cameras/hik_8mm.yaml` | Hikrobot 8mm 相机配置 | cameras | 否 | 否 | 已在目标目录 | `configs/cameras/hik_8mm.yaml` | 高：8mm 内参尚需真实标定确认 |
| `configs/cameras/webcam.yaml` | 普通 USB 摄像头配置 | cameras | 否 | 否 | 已在目标目录 | `configs/cameras/webcam.yaml` | 低 |
| `configs/capture/d455_object_capture_auto.yaml` | D455 自动采集配置 | capture | 是 | 否 | 已在目标目录 | `configs/capture/d455_object_capture_auto.yaml` | 中：仍需硬件 validate |
| `configs/capture/hik_6mm_object_capture_auto.yaml` | Hikrobot 6mm 自动采集配置 | capture | 是 | 否 | 已在目标目录 | `configs/capture/hik_6mm_object_capture_auto.yaml` | 中：曝光和触发模式需现场验证 |
| `configs/capture/hik_8mm_object_capture_auto.yaml` | Hikrobot 8mm 自动采集配置 | capture | 否 | 否 | 已在目标目录 | `configs/capture/hik_8mm_object_capture_auto.yaml` | 高：8mm 内参未完成 |
| `configs/calibration/d455_rgb_calibration.yaml` | D455 RGB 内参/标定配置 | calibration | 是 | 否 | 已在目标目录 | `configs/calibration/d455_rgb_calibration.yaml` | 中：与 D455 历史流程相关 |
| `configs/calibration/hik_6mm_calibration.yaml` | Hikrobot 6mm 标定配置 | calibration | 是 | 否 | 已在目标目录 | `configs/calibration/hik_6mm_calibration.yaml` | 高：真实标定参数会直接影响外参/标签 |
| `configs/calibration/hik_8mm_calibration.yaml` | Hikrobot 8mm 标定配置 | calibration | 否 | 否 | 已在目标目录 | `configs/calibration/hik_8mm_calibration.yaml` | 高：8mm 内参尚未定版 |
| `configs/calibration_hik_6mm.yaml` | 根目录旧 Hik 6mm 标定配置 | calibration | 可能 | 是 | 是 | `configs/legacy/calibration_hik_6mm.yaml` | 高：旧命令可能仍引用 |
| `configs/calibration_hik_8mm.yaml` | 根目录旧 Hik 8mm 标定配置 | calibration | 可能 | 是 | 是 | `configs/legacy/calibration_hik_8mm.yaml` | 高：旧命令可能仍引用 |
| `configs/board_capture.yaml` | D455/动捕标定板采集旧配置 | calibration | 可能 | 是 | 是 | `configs/legacy/board_capture.yaml` | 高：D455 外参历史流程可能引用 |
| `configs/board_capture_gdrive.yaml` | G 盘版标定板采集配置 | calibration | 否 | 是 | 是 | `configs/legacy/board_capture_gdrive.yaml` | 中：应由 paths 机制替代 |
| `configs/object_capture.yaml` | 旧版小车采集配置 | capture | 可能 | 是 | 是 | `configs/legacy/object_capture.yaml` | 高：README/旧命令可能仍引用 |
| `configs/object_capture_auto.yaml` | 根目录自动采集配置 | capture | 可能 | 是 | 是 | `configs/legacy/object_capture_auto.yaml` | 中：已有 `configs/capture/` 新入口 |
| `configs/object_capture_gdrive.yaml` | G 盘版旧采集配置 | capture | 否 | 是 | 是 | `configs/legacy/object_capture_gdrive.yaml` | 中：应由 paths 机制替代 |
| `configs/fzmotion_fixed_camera_current_rigids.yaml` | D455 固定相机/当前刚体自动标签配置 | labeling | 是 | 否 | 是 | `configs/labeling/fzmotion_fixed_camera_current_rigids.yaml` | 高：D455 标签主流程依赖 |
| `configs/fzmotion_fixed_camera_current_rigids_gdrive.yaml` | G 盘版 D455 标签配置 | labeling | 否 | 是 | 暂缓 | `configs/legacy/fzmotion_fixed_camera_current_rigids_gdrive.yaml` | 高：路径替代前不宜动 |
| `configs/fzmotion_hikvision_6mm_current_rigids.yaml` | Hikrobot 6mm 当前刚体标签配置 | labeling | 是 | 否 | 是 | `configs/labeling/fzmotion_hikvision_6mm_current_rigids.yaml` | 高：Hik 外参/标签质量依赖 |
| `configs/fzmotion_fixed_camera_live_v1.yaml` | D455 实时推理配置 | tracking | 是 | 否 | 是 | `configs/tracking/fzmotion_fixed_camera_live_v1.yaml` | 高：现场演示命令可能引用 |
| `configs/fzmotion_fixed_camera_live_v1_gdrive.yaml` | G 盘版实时推理配置 | tracking | 否 | 是 | 暂缓 | `configs/legacy/fzmotion_fixed_camera_live_v1_gdrive.yaml` | 中 |
| `configs/fzmotion_fast_moving_live.yaml` | Fast-moving 实时推理配置 | tracking | 是 | 否 | 是 | `configs/tracking/fzmotion_fast_moving_live.yaml` | 高：后续 demo 依赖 |
| `configs/fzmotion_fast_moving_live_gdrive.yaml` | G 盘版 fast-moving 实时配置 | tracking | 否 | 是 | 暂缓 | `configs/legacy/fzmotion_fast_moving_live_gdrive.yaml` | 中 |
| `configs/kalman_fixed.yaml` | fixed Kalman 参数 | tracking | 是 | 否 | 是 | `configs/tracking/kalman_fixed.yaml` | 低：适合优先复制 |
| `configs/kalman_reliability.yaml` | reliability-aware Kalman 参数 | tracking | 是 | 否 | 是 | `configs/tracking/kalman_reliability.yaml` | 低：适合优先复制 |
| `configs/local_smoke_replay.yaml` | 本地 smoke replay 配置 | replay | 是 | 否 | 是 | `configs/replay/local_smoke_replay.yaml` | 低：适合优先复制 |
| `configs/local_smoke_replay_gdrive.yaml` | G 盘版 smoke replay 配置 | replay | 否 | 是 | 暂缓 | `configs/legacy/local_smoke_replay_gdrive.yaml` | 中：路径机制替代前保留 |
| `configs/session_manifest_template.yaml` | session manifest 模板 | sessions | 是 | 否 | 是 | `configs/sessions/session_manifest_template.yaml` | 低：适合优先复制 |
| `configs/planned_sessions_template.yaml` | 计划采集 session 模板 | sessions | 是 | 否 | 是 | `configs/sessions/planned_sessions_template.yaml` | 低 |
| `configs/real_sessions_first_batch_template.yaml` | 第一批真实 session 模板 | sessions | 是 | 否 | 是 | `configs/sessions/real_sessions_first_batch_template.yaml` | 低 |
| `configs/uav_4m_20_sessions.yaml` | D455 20-session 批处理清单 | sessions | 是 | 否 | 是 | `configs/sessions/uav_4m_20_sessions.yaml` | 中：历史训练集复现依赖 |
| `configs/uav_4m_20_sessions_gdrive.yaml` | G 盘版 20-session 清单 | sessions | 否 | 是 | 暂缓 | `configs/legacy/uav_4m_20_sessions_gdrive.yaml` | 中 |
| `configs/dataset_manifest_template.yaml` | dataset manifest 模板 | datasets | 是 | 否 | 是 | `configs/datasets/dataset_manifest_template.yaml` | 低：适合优先复制 |
| `configs/model_registry_template.yaml` | model registry 模板 | models | 是 | 否 | 是 | `configs/models/model_registry_template.yaml` | 低：适合优先复制 |
| `configs/hikvision_capture_presets.yaml` | Hikrobot 采集参数预设 | cameras | 是 | 否 | 是 | `configs/cameras/hikvision_capture_presets.yaml` | 中：曝光/增益/帧率会影响数据一致性 |
| `configs/color_correction/rgb_wall_reference.yaml` | RGB 背景墙色彩校正实验配置 | color_correction | 否 | 否 | 已在目标目录 | `configs/color_correction/rgb_wall_reference.yaml` | 低：实验性，不接正式 pipeline |

## 2. 推荐目标配置结构

### `configs/paths/`

存放主机和采集笔记本的数据根目录配置：

- `paths_local.yaml`
- `paths_laptop.yaml`

说明：所有数据根目录必须通过 paths config 管理，避免把 `G:\YOLO6D_Car_Data`、`D:\CaptureData` 等路径硬编码到代码或命令模板中。

### `configs/cameras/`

存放相机硬件配置，包括 D455、Hikrobot 6mm、Hikrobot 8mm、Webcam，以及 Hikrobot 参数预设。

推荐内容：

- `d455.yaml`
- `hik_6mm.yaml`
- `hik_8mm.yaml`
- `webcam.yaml`
- `hikvision_capture_presets.yaml`

### `configs/capture/`

存放自动采集任务配置。采集脚本只应关心“采集任务”，具体相机参数应尽量引用 `configs/cameras/`。

当前已有：

- `d455_object_capture_auto.yaml`
- `hik_6mm_object_capture_auto.yaml`
- `hik_8mm_object_capture_auto.yaml`

### `configs/calibration/`

存放 D455 / Hikrobot 内参、外参、标定板参数和标定流程配置。

当前已有：

- `d455_rgb_calibration.yaml`
- `hik_6mm_calibration.yaml`
- `hik_8mm_calibration.yaml`

根目录旧 `calibration_hik_*.yaml` 建议先复制到 `legacy/`，不要直接移动。

### `configs/labeling/`

存放 FzMotion / Mocap / current rigids / auto label 相关配置。

建议未来收口：

- `fzmotion_fixed_camera_current_rigids.yaml`
- `fzmotion_hikvision_6mm_current_rigids.yaml`

这类配置通常绑定相机外参、小车刚体和模型关键点，风险较高，迁移必须保留旧路径兼容。

### `configs/tracking/`

存放 Kalman、reliability-aware Kalman、实时推理和 fast-moving 相关配置。

建议未来收口：

- `kalman_fixed.yaml`
- `kalman_reliability.yaml`
- `fzmotion_fixed_camera_live_v1.yaml`
- `fzmotion_fast_moving_live.yaml`

### `configs/replay/`

存放 smoke replay、offline replay、PnP 回放等配置。

建议未来收口：

- `local_smoke_replay.yaml`

### `configs/evaluation/`

存放 GT evaluation、metrics 和评估输出配置。

当前未确认已有独立 evaluation 配置。后续新增评估 YAML 时优先放入该目录。

### `configs/sessions/`

存放 session 清单、采集计划和 session manifest 模板。

建议未来收口：

- `session_manifest_template.yaml`
- `planned_sessions_template.yaml`
- `real_sessions_first_batch_template.yaml`
- `uav_4m_20_sessions.yaml`

### `configs/datasets/`

存放 dataset manifest 模板和数据集构建配置。

建议未来收口：

- `dataset_manifest_template.yaml`

### `configs/models/`

存放 model registry 模板和小型模型注册配置。注意不要把 `.pt`、`.onnx` 等权重放进 Git。

建议未来收口：

- `model_registry_template.yaml`

### `configs/color_correction/`

存放 RGB 背景墙、Gamma、HSV、CCM、白平衡等色彩校正实验配置。

当前已有：

- `rgb_wall_reference.yaml`

### `configs/legacy/`

存放短期需要保留但不推荐继续新增使用的旧配置，例如根目录旧采集配置、根目录旧标定配置和 `_gdrive.yaml` 兼容配置。

注意：`legacy/` 不是垃圾桶，不能随便删除。放入 legacy 前应先确认旧命令、README、docs、主机/笔记本流程都已经切到新入口。

## 3. 优先迁移候选

### High

1. `paths_local.yaml` / `paths_laptop.yaml`
   - 建议进入 `configs/paths/`。
   - 原因：主机和笔记本路径差异是当前最容易出错的点。
   - 风险：所有带 `--paths-config` 的命令都可能引用旧路径，必须复制兼容，不可直接移动。

2. `fzmotion_*`
   - 建议进入 `configs/labeling/` 或 `configs/tracking/`，按用途拆分。
   - 原因：这类配置绑定外参、刚体、模型、自动标签和实时推理。
   - 风险：直接移动会破坏打标签、live pose、fast-moving demo。

3. `calibration_hik_6mm.yaml` / `calibration_hik_8mm.yaml`
   - 建议最终进入 `configs/legacy/`。
   - 原因：已有 `configs/calibration/hik_6mm_calibration.yaml` 和 `hik_8mm_calibration.yaml`。
   - 风险：旧命令可能仍使用根目录文件。

### Medium

1. `object_capture.yaml` / `object_capture_auto.yaml`
   - 建议最终进入 `configs/legacy/`，新流程使用 `configs/capture/`。
   - 风险：历史采集命令和 README 仍可能引用。

2. `*_gdrive.yaml`
   - 建议暂缓移动，最终 legacy 化。
   - 原因：它们应逐步被 paths config 机制替代。
   - 风险：主机旧命令可能依赖。

3. `uav_4m_20_sessions.yaml`
   - 建议进入 `configs/sessions/`。
   - 风险：D455 v1/v2 数据集复现可能依赖旧路径。

4. `hikvision_capture_presets.yaml`
   - 建议进入 `configs/cameras/`。
   - 风险：采集参数对图像亮度和运动模糊影响大，需要保证采集脚本引用一致。

### Low

1. `kalman_fixed.yaml` / `kalman_reliability.yaml`
   - 建议进入 `configs/tracking/`。
   - 风险低，适合作为下一轮低风险复制候选。

2. `local_smoke_replay.yaml`
   - 建议进入 `configs/replay/`。
   - 风险低，适合作为复制后 smoke test 验证对象。

3. `session_manifest_template.yaml`
   - 建议进入 `configs/sessions/`。

4. `dataset_manifest_template.yaml`
   - 建议进入 `configs/datasets/`。

5. `model_registry_template.yaml`
   - 建议进入 `configs/models/`。

## 4. 复制兼容式迁移方案

当前不能直接移动 YAML，因为旧命令、README、docs、主机脚本和笔记本流程仍可能引用旧路径。推荐采用复制兼容式迁移。

### Stage 1：复制，不移动

- 把低风险根目录旧配置复制到新目标目录。
- 旧文件保留。
- 新文档和新命令推荐使用新路径。
- 旧路径短期继续可用。
- 对复制后的配置跑 `--validate-config`、smoke replay 和 Git diff 检查。

适合 Stage 1 的候选：

- `configs/paths_local.yaml` -> `configs/paths/paths_local.yaml`
- `configs/paths_laptop.yaml` -> `configs/paths/paths_laptop.yaml`
- `configs/kalman_fixed.yaml` -> `configs/tracking/kalman_fixed.yaml`
- `configs/kalman_reliability.yaml` -> `configs/tracking/kalman_reliability.yaml`
- `configs/local_smoke_replay.yaml` -> `configs/replay/local_smoke_replay.yaml`
- `configs/session_manifest_template.yaml` -> `configs/sessions/session_manifest_template.yaml`
- `configs/dataset_manifest_template.yaml` -> `configs/datasets/dataset_manifest_template.yaml`
- `configs/model_registry_template.yaml` -> `configs/models/model_registry_template.yaml`

### Stage 2：旧文件标注 legacy

- 旧配置顶部加注释，说明推荐新路径。
- 不删除旧文件。
- 不改变旧文件内容语义。
- 至少经过 1-2 个实验周期后，再决定是否移动到 `configs/legacy/`。

适合 Stage 2 的候选：

- `configs/object_capture.yaml`
- `configs/object_capture_auto.yaml`
- `configs/object_capture_gdrive.yaml`
- `configs/board_capture.yaml`
- `configs/board_capture_gdrive.yaml`
- `configs/calibration_hik_6mm.yaml`
- `configs/calibration_hik_8mm.yaml`
- `configs/*_gdrive.yaml`

### Stage 3：旧路径 wrapper / deprecation

- 如果脚本支持新路径，README 和 docs 也已切到新路径，则旧配置可以进入归档或 legacy。
- 删除必须人工确认，且需要单独任务。
- 任何删除前都要先跑完整验证命令，并确认主机和笔记本都不再引用旧路径。

## 5. 下一轮建议执行内容

建议下一轮只做低风险配置复制，不移动、不删除、不改旧配置：

1. 新增目录：
   - `configs/paths/`
   - `configs/tracking/`
   - `configs/replay/`
   - `configs/labeling/`
   - `configs/sessions/`
   - `configs/datasets/`
   - `configs/models/`
   - `configs/legacy/`

2. 复制而不是移动：
   - `configs/paths_local.yaml` -> `configs/paths/paths_local.yaml`
   - `configs/paths_laptop.yaml` -> `configs/paths/paths_laptop.yaml`
   - `configs/kalman_fixed.yaml` -> `configs/tracking/kalman_fixed.yaml`
   - `configs/kalman_reliability.yaml` -> `configs/tracking/kalman_reliability.yaml`
   - `configs/local_smoke_replay.yaml` -> `configs/replay/local_smoke_replay.yaml`
   - `configs/session_manifest_template.yaml` -> `configs/sessions/session_manifest_template.yaml`
   - `configs/dataset_manifest_template.yaml` -> `configs/datasets/dataset_manifest_template.yaml`
   - `configs/model_registry_template.yaml` -> `configs/models/model_registry_template.yaml`

3. 暂不复制有风险的外参/采集/硬件强绑定配置，只在文档中建议：
   - `configs/fzmotion_*.yaml`
   - `configs/*_gdrive.yaml`
   - `configs/object_capture*.yaml`
   - `configs/calibration_hik_*.yaml`
   - `configs/board_capture*.yaml`

4. 更新 `docs/index.md` 和 `docs/setup/common_commands.md`，增加新配置路径入口。

## 6. 风险清单

- 不能直接移动 YAML：大量旧命令、README、docs、主机/笔记本流程仍引用根目录配置。
- 旧命令受影响范围：采集、标定、自动标签、replay、live pose、训练前数据准备。
- 强硬件相关配置：`calibration_hik_*`、`fzmotion_*`、`hik_*_calibration.yaml`、`hik_*_object_capture_auto.yaml`。
- D455/Hik 外参风险：`fzmotion_fixed_camera_current_rigids.yaml`、`fzmotion_hikvision_6mm_current_rigids.yaml` 与刚体、相机外参、模型关键点强绑定。
- paths 混乱风险：`paths_local.yaml` 和 `paths_laptop.yaml` 如果混用，会导致数据写到错误机器或错误盘。
- 主机/笔记本路径风险：主机推荐 `G:\YOLO6D_Car_Data`，笔记本推荐 `D:\CaptureData`，不能在命令中互相复制硬编码路径。
- `_gdrive.yaml` 风险：它们是路径机制过渡产物，短期保留，长期应由 paths config 替代。

## 7. 未来验证命令建议

配置复制真正执行后，建议至少运行：

```powershell
python .\scripts\capture_object_samples.py --config .\configs\capture\d455_object_capture_auto.yaml --paths-config .\configs\paths\paths_laptop.yaml --validate-config
```

```powershell
python .\scripts\capture_object_samples.py --config .\configs\capture\hik_6mm_object_capture_auto.yaml --paths-config .\configs\paths\paths_laptop.yaml --validate-config
```

```powershell
python .\scripts\capture_object_samples.py --config .\configs\capture\hik_8mm_object_capture_auto.yaml --paths-config .\configs\paths\paths_laptop.yaml --validate-config
```

```powershell
python .\scripts\smoke_replay_pipeline.py --config .\configs\replay\local_smoke_replay.yaml --max-frames 3
```

如果后续脚本支持新配置路径，还应补充：

```powershell
python .\scripts\smoke_replay_pipeline.py --config .\configs\replay\local_smoke_replay.yaml --max-frames 3
```

本轮只写建议，不运行真实采集，不连接相机，不训练模型。

## Phase B2 已执行：低风险复制兼容迁移

本阶段只执行“复制兼容迁移”，不移动、不删除、不重命名旧配置文件。旧路径继续保留，旧命令仍应继续可用；新路径用于后续文档和新命令逐步切换。

### 本轮新增目录

- `configs/paths/`
- `configs/tracking/`
- `configs/replay/`
- `configs/sessions/`
- `configs/datasets/`
- `configs/models/`
- `configs/legacy/`

### 本轮复制的低风险配置

| 旧路径 | 新路径 | 说明 |
| --- | --- | --- |
| `configs/paths_local.yaml` | `configs/paths/paths_local.yaml` | 主机路径配置兼容副本 |
| `configs/paths_laptop.yaml` | `configs/paths/paths_laptop.yaml` | 采集笔记本路径配置兼容副本 |
| `configs/kalman_fixed.yaml` | `configs/tracking/kalman_fixed.yaml` | fixed Kalman 参数兼容副本 |
| `configs/kalman_reliability.yaml` | `configs/tracking/kalman_reliability.yaml` | reliability-aware Kalman 参数兼容副本 |
| `configs/local_smoke_replay.yaml` | `configs/replay/local_smoke_replay.yaml` | smoke replay 配置兼容副本 |
| `configs/session_manifest_template.yaml` | `configs/sessions/session_manifest_template.yaml` | session manifest 模板兼容副本 |
| `configs/dataset_manifest_template.yaml` | `configs/datasets/dataset_manifest_template.yaml` | dataset manifest 模板兼容副本 |
| `configs/model_registry_template.yaml` | `configs/models/model_registry_template.yaml` | model registry 模板兼容副本 |

### 当前状态

- 新旧路径短期并存。
- 旧配置文件仍然保留在 `configs/` 根目录。
- 本轮没有处理任何相机、标定、外参、真实采集或历史路径强绑定配置。
- 后续文档可以逐步推荐使用新路径，但短期不要删除旧路径。

### Phase B2.6 补充：replay 配置相对路径修复

`configs/local_smoke_replay.yaml` 不能只做机械复制。该配置内部包含 `models/...` 和 `data/examples/...` 等相对路径；复制到 `configs/replay/` 后，现有配置加载逻辑会以新配置位置推导解析根，导致这些路径被解析到 `configs/models/...` 或 `configs/data/...`。

B2.6 已只修改新配置 `configs/replay/local_smoke_replay.yaml`，将内部相对路径调整为：

- `object_model.model_json_path: ../models/car_custom_keypoints_12_migrated_200xx_exact.json`
- `yolo6d.replay_json_path: ../data/examples/custom_model_12pt_predictions.json`

旧配置 `configs/local_smoke_replay.yaml` 未修改。修复后新旧 replay smoke 均已通过。

后续迁移其他配置时，不能只检查文件是否复制成功，还必须检查 YAML 内部所有相对路径是否依赖配置文件位置，例如模型、数据集、示例 replay、输出目录、标定文件和外参文件路径。

### 本轮暂未处理的高风险配置

- `configs/fzmotion_*.yaml`
- `configs/*_gdrive.yaml`
- `configs/object_capture*.yaml`
- `configs/board_capture*.yaml`
- `configs/calibration_hik_*.yaml`
- `configs/calibration/*.yaml`
- `configs/cameras/*.yaml`
- `configs/capture/*.yaml`
- `configs/color_correction/*.yaml`

这些配置涉及外参、相机、真实采集、历史路径或仍在实验中的功能，需要人工确认后再进入下一阶段。

### 下一阶段建议：Phase B3

Phase B3 建议只做“旧配置标注 legacy”，仍然不删除旧配置。可以在低风险旧根配置顶部增加注释，提示推荐新路径；对于高风险配置，只先在文档中标注，不直接改文件内容。

## Phase B3 已执行：新路径推荐化与低风险旧配置 legacy 标注

本阶段继续采用安全兼容策略：不移动、不删除、不重命名任何配置文件，只在低风险旧根配置顶部增加 legacy 注释，并在 README / docs 中逐步推荐使用新的 `configs/` 子目录路径。

### 已标注 legacy 的低风险旧根配置

以下旧配置仍保留在 `configs/` 根目录，用于兼容旧命令和旧文档；新任务优先使用右侧推荐路径。

| 旧配置 | 推荐新路径 | 说明 |
| --- | --- | --- |
| `configs/paths_local.yaml` | `configs/paths/paths_local.yaml` | 主机路径配置 |
| `configs/paths_laptop.yaml` | `configs/paths/paths_laptop.yaml` | 采集笔记本路径配置 |
| `configs/kalman_fixed.yaml` | `configs/tracking/kalman_fixed.yaml` | fixed Kalman 参数 |
| `configs/kalman_reliability.yaml` | `configs/tracking/kalman_reliability.yaml` | reliability-aware Kalman 参数 |
| `configs/local_smoke_replay.yaml` | `configs/replay/local_smoke_replay.yaml` | 本地 smoke replay 配置 |
| `configs/session_manifest_template.yaml` | `configs/sessions/session_manifest_template.yaml` | session manifest 模板 |
| `configs/dataset_manifest_template.yaml` | `configs/datasets/dataset_manifest_template.yaml` | dataset manifest 模板 |
| `configs/model_registry_template.yaml` | `configs/models/model_registry_template.yaml` | model registry 模板 |

### 文档推荐路径调整

- README 中的常用路径示例已优先指向 `configs/paths/paths_local.yaml`、`configs/paths/paths_laptop.yaml` 和 `configs/replay/local_smoke_replay.yaml`。
- `docs/setup/common_commands.md` 中的常用命令已优先使用 `configs/paths/paths_local.yaml`。
- `docs/index.md` 中已说明 configs 当前处于新旧路径并存、旧根配置 legacy 标注阶段。

### 本阶段仍未处理的高风险配置

以下配置继续保持现状，不在 Phase B3 中添加 legacy 注释，也不推荐贸然移动或改写：

- `configs/fzmotion_*.yaml`
- `configs/*_gdrive.yaml`
- `configs/object_capture*.yaml`
- `configs/board_capture*.yaml`
- `configs/calibration_hik_*.yaml`
- `configs/calibration/*.yaml`
- `configs/cameras/*.yaml`
- `configs/capture/*.yaml`
- `configs/color_correction/*.yaml`

这些配置涉及真实相机、外参、标定、采集流程或仍在实验中的功能，需要在后续阶段逐项确认。

### 下一阶段建议：Phase B4

Phase B4 可以开始做文档和命令的更系统回归：确认 README、常用命令、采集流程和训练流程是否都优先使用新路径；同时继续保留旧配置，至少经过 1-2 个完整实验周期后再讨论是否真正归档或删除旧根配置。
