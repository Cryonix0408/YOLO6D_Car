# Evaluate Pose Results

`scripts/evaluate_pose_results.py` compares raw PnP pose and filtered Kalman pose from a replay CSV.

## Input CSV

The CSV should contain raw pose columns:

```text
raw_tx raw_ty raw_tz raw_rx raw_ry raw_rz
```

and filtered pose columns:

```text
filtered_tx filtered_ty filtered_tz filtered_rx filtered_ry filtered_rz
```

It should also contain either `timestamp_s`, `timestamp`, or `frame_id` / `frame_index`. If no timestamp column exists, the script generates timestamps from frame id and `--default-fps`.

If filtered columns are missing, the script reports:

```text
filtered pose columns not found; run replay with --kalman-config first.
```

## Run

```powershell
D:\Envs\yolo6d\python.exe scripts\evaluate_pose_results.py --input-csv outputs\replay_runs\latest\pose_results.csv --output-dir results\evaluation\latest --paths-config configs\paths_local.yaml --plot
```

For a local ignored smoke CSV in the repo:

```powershell
D:\Envs\yolo6d\python.exe scripts\evaluate_pose_results.py --input-csv outputs\kalman_smoke.csv --output-dir outputs\evaluation\kalman_smoke --plot
```

## Outputs

```text
metrics_summary.json
metrics_summary.csv
evaluation_report.md
```

With `--plot`, the script also tries to write:

```text
translation_xyz_raw_vs_filtered.png
rotation_rvec_raw_vs_filtered.png
translation_velocity.png
translation_acceleration.png
jitter_comparison.png
tracking_state_timeline.png
```

If matplotlib is missing, metrics are still written and plotting is skipped with a warning.

## Metrics

Jitter is the RMS frame-to-frame pose delta norm. Lower jitter means less frame-to-frame shaking.

Velocity smoothness uses the standard deviation of translation velocity norm. Lower is smoother.

Acceleration smoothness uses the standard deviation of translation acceleration norm. Lower is smoother and usually indicates less abrupt motion.

Positive improvement percentages mean the filtered pose is smoother than raw pose.

## Interpreting Raw vs Filtered

- Raw pose should respond immediately but may jitter.
- Filtered pose should reduce jitter and acceleration spikes.
- If filtered metrics are worse, the Kalman Q/R values may be too stiff, too loose, or mismatched to the motion speed.

## Future Mocap GT

`--gt-csv` is reserved. Passing it currently records a TODO warning instead of crashing. Later it should compare raw/filtered pose against FzMotion ground truth.
## Code Reading Notes

- `scripts/evaluate_pose_results.py` 是 CLI 入口。
- `src/yolo6d_car/evaluation/trajectory.py` 负责读取 pose CSV。
- `src/yolo6d_car/evaluation/metrics.py` 负责 jitter / velocity / acceleration 指标。
- `src/yolo6d_car/evaluation/gt_metrics.py` 负责 `gt_pose.csv` 对比。

结果判断：

- filtered jitter 低于 raw jitter，通常说明滤波更平滑。
- 平滑不等于准确；是否准确需要 GT，例如 `gt_pose.csv`。
- smoke 数据帧数少，只能确认流程能跑。

