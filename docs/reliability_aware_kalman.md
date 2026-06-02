# Reliability-Aware Kalman Replay

This is the first rule-based upgrade after the fixed 12D constant-velocity
Kalman baseline. It keeps the same state model, but changes how strongly the
filter trusts each PnP measurement.

## Why Fixed KF Is Not Enough

A fixed Kalman filter uses one constant measurement noise matrix `R`. That is a
good baseline, but replay measurements are not equally reliable: a frame with
low confidence, high reprojection error, or a sudden implausible pose jump
should influence the filter less than a clean frame.

## Core Idea

The replay pipeline now supports:

```powershell
D:\Envs\yolo6d\python.exe scripts\smoke_replay_pipeline.py --config configs\local_smoke_replay.yaml --max-frames 3 --kalman-config configs\kalman_reliability.yaml
```

The insertion point is unchanged:

```text
YOLO Pose / JSON replay keypoints
PnP raw rvec/tvec
ReliabilityEstimator
PoseKalmanFilter with dynamic R
filtered rvec/tvec
CSV output
```

## Signals

- `confidence`: low confidence reduces reliability and can reject a measurement.
- `reprojection_error`: small error means the PnP pose agrees with keypoints;
  very large error can reject the measurement.
- `blur_score`: supported by the estimator, disabled in replay by default
  because replay smoke frames are synthetic black frames.
- `pose_jump`: large translation or rotation-vector jumps from the previous
  accepted measurement reduce reliability or trigger reject.

Missing fields use safe defaults from `configs/kalman_reliability.yaml` and log
a warning instead of crashing.

## Dynamic R Scale

`dynamic_R_scale` multiplies the base Kalman measurement noise for the current
correction only.

- Smaller scale: trust current PnP more.
- Larger scale: trust prediction more and measurement less.
- Rejected measurement: skip correction and run predict-only.

The scale is clamped by:

```yaml
reliability:
  dynamic_R:
    min_scale: 0.5
    max_scale: 50.0
```

## Gating

Measurement rejection can happen when:

- `confidence < min_confidence`
- `reprojection_error >= reject_px`
- translation jump or rotation jump exceeds reject thresholds

When rejected, the CSV records `reject_reason`, `valid_measurement=false`, and
the Kalman filter enters predict-only behavior for that frame.

## CSV Fields

Reliability-aware replay adds:

```text
reliability_score
dynamic_R_scale
valid_measurement
reject_reason
confidence_used
reprojection_error_used
blur_score_used
translation_jump_m
rotation_jump_rad
```

The existing fixed-KF fields remain:

```text
raw_tx raw_ty raw_tz raw_rx raw_ry raw_rz
filtered_tx filtered_ty filtered_tz filtered_rx filtered_ry filtered_rz
reprojection_error
tracking_state
kalman_valid_measurement
```

## Evaluation

Use the existing evaluator on any replay CSV that was saved with Kalman fields:

```powershell
D:\Envs\yolo6d\python.exe scripts\evaluate_pose_results.py ^
  --input-csv outputs\replay_runs\latest\pose_results.csv ^
  --output-dir results\evaluation\latest ^
  --paths-config configs\paths_local.yaml ^
  --plot
```

If reliability fields exist, `evaluation_report.md` also summarizes:

- mean/min/max reliability score
- mean dynamic R scale
- rejected measurement frames
- top reject reasons

## Tuning

- Increase `base_position_measurement_noise` or
  `base_rotation_measurement_noise` if filtered pose is still too jittery.
- Lower them if the filter lags too much.
- Reduce `reprojection_error.bad_px` or `pose_jump.translation_bad_m` to make
  the filter more skeptical.
- Increase reject thresholds if too many frames become predict-only.

## Current Limits

This is not a learned uncertainty model. It does not yet use keypoint-level
uncertainty, mocap GT-based tuning, or speed-dependent analysis. Blur is
implemented but disabled for replay until real image frames are available.

Future upgrades can add learned uncertainty, per-keypoint covariance,
mocap-ground-truth calibration, and reliability analysis by object speed.
## Code Reading Notes

- 核心代码在 `src/yolo6d_car/tracking/reliability_estimator.py`。
- `reliability_score` 越高，measurement 越可信。
- `dynamic_R_scale` 越大，Kalman measurement noise R 越大，滤波器越不相信当前 PnP。
- reprojection error、confidence、pose jump 是当前最重要的规则信号。

常见错误：

- 把 reliability-aware KF 当成学习模型。当前版本只是规则型 estimator。
- 在 smoke 数据上过度解读指标。真实 fast-moving session 才能说明性能。
