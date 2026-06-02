# Session Manifest Workflow

The session manifest is the project index for real capture sessions. It keeps
code on `D:\Research\YOLO6D_Car` and large data under `G:\YOLO6D_Car_Data`,
while giving every capture a stable ID and standard metadata.

## Why It Exists

Each real experiment produces images or videos, mocap CSV, generated labels,
replay configs, training splits, and ablation reports. A manifest keeps those
paths and experimental conditions together so later scripts can automate:

- automatic labeling,
- dataset construction,
- replay smoke tests,
- Kalman ablation,
- paper result grouping.

## session_id Naming

Use:

```text
YYYY-MM-DD_object_motion_index
```

Examples:

```text
2026-05-30_car_static_001
2026-05-30_car_fast_lateral_001
2026-05-30_car_rotation_002
```

Keep IDs stable once data exists on disk.

## Fields

Top-level `dataset` fields:

- `name`: dataset name, such as `car_fast6d_v1`.
- `description`: short human-readable purpose.
- `data_root`: expected large-data root.
- `created_by`: dataset owner.
- `version`: dataset version.

Per-session fields:

- `session_id`, `date`, `object`
- `camera.type`, `camera.lens`, `camera.intrinsics`
- `mocap.enabled`, `mocap.csv_path`, `mocap.camera_rigid`,
  `mocap.object_rigid`
- `capture.root`, `capture.images_dir`, `capture.videos_dir`,
  `capture.metadata`
- `motion.type`, `motion.speed_level`, `motion.occlusion`,
  `motion.lighting`, `motion.background`
- `outputs.auto_labels`, `outputs.dataset_split`,
  `outputs.replay_config`, `outputs.ablation_run_name`

Paths like `captures/...`, `FZmotion_Data/...`, `outputs/...`, and
`results/...` resolve under `G:\YOLO6D_Car_Data` when using
`--paths-config configs\paths_local.yaml`.

## Add a New Session

1. Copy one session block in `configs\session_manifest_template.yaml`.
2. Change `session_id`, `date`, motion fields, camera type/lens, and split.
3. Point `mocap.csv_path` to the expected FzMotion CSV.
4. Point `capture.root` to the capture folder.
5. Choose `outputs.dataset_split` as `train`, `val`, `test`, or another
   explicit experiment split.

No real files are required for basic validation.

## Validate

```powershell
D:\Envs\yolo6d\python.exe scripts\manage_sessions.py ^
  --manifest configs\session_manifest_template.yaml ^
  --paths-config configs\paths_local.yaml ^
  --action validate
```

## Summary

```powershell
D:\Envs\yolo6d\python.exe scripts\manage_sessions.py ^
  --manifest configs\session_manifest_template.yaml ^
  --paths-config configs\paths_local.yaml ^
  --action summary
```

## Export Session Table

```powershell
D:\Envs\yolo6d\python.exe scripts\manage_sessions.py ^
  --manifest configs\session_manifest_template.yaml ^
  --paths-config configs\paths_local.yaml ^
  --action export-table ^
  --output results\session_tables\session_manifest_summary.csv
```

This creates a CSV table for planning and experiment tracking.

## Generate Replay Configs

```powershell
D:\Envs\yolo6d\python.exe scripts\manage_sessions.py ^
  --manifest configs\session_manifest_template.yaml ^
  --paths-config configs\paths_local.yaml ^
  --action generate-replay-configs
```

Generated files go to each session's `outputs.replay_config`, for example:

```text
G:\YOLO6D_Car_Data\outputs\replay_configs\2026-05-30_car_fast_lateral_001.yaml
```

The generated replay configs are skeletons. After automatic labels or replay
predictions exist, fill `yolo6d.replay_json_path`.

## Batch Dry-Run Ablation

```powershell
D:\Envs\yolo6d\python.exe scripts\manage_sessions.py ^
  --manifest configs\session_manifest_template.yaml ^
  --paths-config configs\paths_local.yaml ^
  --action run-ablation ^
  --speed-level fast ^
  --dry-run
```

Filters:

- `--speed-level fast`
- `--motion-type lateral`
- `--split test`
- `--camera-type hikrobot`
- `--lens 6mm`

Dry-run prints the commands without running large experiments.

## Paper Experiment Groups

Use manifest fields to group results by:

- `static`
- `slow`
- `medium`
- `fast`
- `occlusion`
- `low-light`
- `rotation`
- `approach`
- `receding`

The same manifest can drive dataset split tables and ablation result tables.
## Code Reading Notes

- `src/yolo6d_car/session_manifest.py` 是 manifest 的核心逻辑。
- `scripts/manage_sessions.py` 是命令行入口。
- session 表示“一次采集”，不是训练集，也不是模型。
- `outputs.dataset_split` 决定这个 session 后续进入 train / val / test 的建议 split。

常见错误：

- `session_id` 重复。
- `camera.lens` 和 `camera.intrinsics` 不匹配。
- `mocap.camera_rigid` / `mocap.object_rigid` 和 FzMotion CSV 中的刚体名不一致。
