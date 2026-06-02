# Kalman Ablation Workflow

This workflow compares three replay modes without a real camera or new data:

1. `raw_pnp`: raw replay/PnP output, no Kalman config.
2. `fixed_kf`: 12D constant-velocity Kalman filter with fixed measurement noise.
3. `reliability_kf`: the same Kalman filter with rule-based dynamic
   measurement noise and gating.

## Why Run Ablation

Ablation separates the value of each tracking layer. It answers:

- how jittery the raw PnP pose is,
- whether fixed Kalman filtering smooths the trajectory,
- whether reliability-aware measurement weighting improves robustness over the
  fixed baseline.

## Smoke Ablation

```powershell
D:\Envs\yolo6d\python.exe scripts\run_kalman_ablation.py ^
  --config configs\local_smoke_replay.yaml ^
  --run-name smoke_kalman_ablation ^
  --max-frames 3 ^
  --plot
```

## G-Drive Ablation

```powershell
D:\Envs\yolo6d\python.exe scripts\run_kalman_ablation.py ^
  --config configs\local_smoke_replay_gdrive.yaml ^
  --paths-config configs\paths_local.yaml ^
  --run-name smoke_kalman_ablation_gdrive ^
  --max-frames 3 ^
  --plot
```

With `--paths-config`, relative `outputs/...` and `results/...` paths resolve
under `G:\YOLO6D_Car_Data`.

## Output Structure

Replay CSV files:

```text
outputs/ablation_runs/<run_name>/raw_pnp/pose_results.csv
outputs/ablation_runs/<run_name>/fixed_kf/pose_results.csv
outputs/ablation_runs/<run_name>/reliability_kf/pose_results.csv
```

Evaluation reports:

```text
results/ablation_reports/<run_name>/raw_pnp/
results/ablation_reports/<run_name>/fixed_kf/
results/ablation_reports/<run_name>/reliability_kf/
results/ablation_reports/<run_name>/ablation_summary.csv
results/ablation_reports/<run_name>/ablation_summary.json
results/ablation_reports/<run_name>/ablation_summary.md
```

Each method directory contains the regular evaluator outputs:

```text
metrics_summary.json
metrics_summary.csv
evaluation_report.md
*.png, if --plot succeeds
```

## Reading ablation_summary.csv

The main columns are:

- `method`
- `total_frames`
- `raw_translation_jitter`
- `filtered_translation_jitter`
- `raw_rotation_jitter`
- `filtered_rotation_jitter`
- `raw_translation_velocity_std`
- `filtered_translation_velocity_std`
- `raw_translation_acceleration_std`
- `filtered_translation_acceleration_std`
- `jitter_reduction_percent`
- `acceleration_smoothness_improvement_percent`
- `predict_only_frames`
- `lost_frames`
- `rejected_measurement_frames`
- `mean_reliability_score`
- `mean_dynamic_R_scale`

`raw_pnp` has no filtered pose, so filtered columns are blank. `fixed_kf` has
filtered pose but no reliability fields. `reliability_kf` should populate both
filtered pose and reliability summaries.

## Paper Table Use

For a paper table, use the same script on the final fast-moving replay config
and report the summary metrics by method. The smoke ablation is only a pipeline
check because it uses very few frames.

Recommended table columns:

- method,
- translation jitter,
- rotation jitter,
- velocity std,
- acceleration std,
- predict-only frames,
- rejected measurement frames.

## Reusing on Real Fast-Moving Data

After collecting and labeling real data, point `--config` to the replay YAML for
that session and increase `--max-frames` or omit it if the script is extended to
support full replay. Keep the same `--run-name` convention, for example:

```powershell
D:\Envs\yolo6d\python.exe scripts\run_kalman_ablation.py ^
  --config configs\fast_moving_replay_gdrive.yaml ^
  --paths-config configs\paths_local.yaml ^
  --run-name fast_moving_session_001 ^
  --max-frames 300 ^
  --plot
```

The same report structure can then feed experiment logs and paper tables.
## Code Reading Notes

- 入口脚本是 `scripts/run_kalman_ablation.py`。
- 它会依次跑 raw_pnp、fixed_kf、reliability_kf。
- 每种方法都会调用 replay，再调用 `evaluate_pose_results.py`。
- `ablation_summary.csv` 可以直接改造成论文表格，但 smoke 数据不能代表真实性能。
