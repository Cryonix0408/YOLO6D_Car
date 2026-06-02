# Mocap GT Evaluation

`scripts/evaluate_pose_results.py` can optionally compare replay pose output against a preprocessed mocap ground-truth pose CSV.

This first version does **not** parse raw FzMotion CSV directly. Convert raw mocap data to a simple `gt_pose.csv` first.

## Supported GT Format

Required columns:

```text
timestamp
gt_tx
gt_ty
gt_tz
gt_rx
gt_ry
gt_rz
```

The GT pose should be expressed in the same coordinate convention as replay output:

- translation in meters
- rotation as Rodrigues rotation vector in radians
- timestamps in seconds

## Run

```powershell
D:\Envs\yolo6d\python.exe scripts\evaluate_pose_results.py `
  --input-csv outputs\replay_runs\session_001\pose_results.csv `
  --gt-csv outputs\gt_pose\session_001_gt_pose.csv `
  --output-dir results\evaluation\session_001 `
  --paths-config configs\paths_local.yaml `
  --max-time-diff-s 0.03 `
  --plot
```

With `configs\paths_local.yaml`, relative `outputs\...` and `results\...` paths resolve under `G:\YOLO6D_Car_Data`.

## Timestamp Alignment

Predicted poses are matched to GT poses by nearest timestamp.

`--max-time-diff-s` controls the largest allowed timestamp gap. The default is `0.03` seconds. Frames without a GT match inside this window are ignored for GT metrics.

## Outputs

Existing raw/filtered smoothness outputs are unchanged:

```text
metrics_summary.json
metrics_summary.csv
evaluation_report.md
```

When `--gt-csv` is provided, additional files are created:

```text
gt_metrics_summary.json
gt_metrics_summary.csv
gt_error_timeseries.csv
gt_evaluation_report.md
```

If `--plot` is enabled:

```text
gt_translation_raw_filtered.png
gt_rotation_raw_filtered.png
gt_translation_error_over_time.png
gt_rotation_error_over_time.png
gt_error_summary.png
```

## Metrics

The GT report includes raw-vs-GT and filtered-vs-GT metrics:

- translation RMSE
- ATE, computed as RMSE of translation error norm
- rotation error mean / median / max
- RPE translation mean / median / max
- RPE rotation mean / median / max
- per-axis translation RMSE
- per-axis mean translation error
- matched frame count and timestamp gap statistics

## Interpretation

Raw pose evaluates the direct PnP output.

Filtered pose evaluates the Kalman-filtered trajectory. If filtered columns are missing, the script still reports raw-vs-GT metrics and writes a warning telling you to rerun replay with `--kalman-config`.

For smoke data with only a few frames, RPE and smoothness numbers are mainly a pipeline check. Real fast-motion conclusions should use full sessions.

## Raw FzMotion CSV

If you pass a raw FzMotion CSV, the script will reject it with a clear message and print the first headers. That is expected. First convert raw mocap into:

```text
timestamp,gt_tx,gt_ty,gt_tz,gt_rx,gt_ry,gt_rz
```

Then rerun this evaluation.
## Code Reading Notes

- GT 对比入口仍然是 `scripts/evaluate_pose_results.py`。
- 第一版 GT 格式必须是预处理后的 `gt_pose.csv`。
- 原始 FzMotion CSV 需要先转换，当前不会直接解析复杂原始格式。
- ATE/RPE 评估的是准确度；jitter/smoothness 评估的是轨迹稳定性。
