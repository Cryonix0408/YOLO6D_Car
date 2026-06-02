# Fixed Kalman Filter in Replay

This is the first runtime integration of the tracking package. It adds an optional fixed Kalman Filter stage after raw PnP pose recovery in replay mode.

Default behavior is unchanged. The filter runs only when a command passes:

```powershell
--kalman-config configs\kalman_fixed.yaml
```

## Where The Filter Is Inserted

Replay pipeline order:

```text
JSON replay keypoints
  -> PnP raw 6DoF pose
  -> optional fixed Kalman Filter
  -> JSON/CSV output
```

The Kalman stage does not replace the PnP solver. It consumes the raw PnP pose as a measurement and produces a separate filtered pose.

## Raw Pose vs Filtered Pose

Raw pose:

- Direct output of the PnP stage for the current frame.
- Translation is in meters.
- Rotation is stored internally as a rotation matrix.
- CSV Kalman output writes rotation as OpenCV Rodrigues vector components `rx ry rz` in radians.

Filtered pose:

- Output of the fixed 12D constant-velocity Kalman Filter.
- State:

```text
[px, py, pz, vx, vy, vz, rx, ry, rz, wx, wy, wz]
```

- Measurement:

```text
[px, py, pz, rx, ry, rz]
```

## Smoke Test

Baseline replay smoke test:

```powershell
D:\Envs\yolo6d\python.exe scripts\smoke_replay_pipeline.py --config configs\local_smoke_replay.yaml --max-frames 3
```

Replay smoke test with fixed Kalman enabled:

```powershell
D:\Envs\yolo6d\python.exe scripts\smoke_replay_pipeline.py --config configs\local_smoke_replay.yaml --max-frames 3 --kalman-config configs\kalman_fixed.yaml
```

## CSV Output

When a config has `output.save_csv` enabled and `--kalman-config` is passed, the CSV contains:

```text
existing prediction_* and mocap_* fields
raw_tx raw_ty raw_tz
raw_rx raw_ry raw_rz
filtered_tx filtered_ty filtered_tz
filtered_rx filtered_ry filtered_rz
reprojection_error
tracking_state
kalman_valid_measurement
```

`tracking_state` values:

- `INIT`: the filter has not received its first valid measurement.
- `TRACKING`: a valid raw PnP measurement was used for correction.
- `PREDICT_ONLY`: no valid measurement was used, so the filter only predicted.
- `LOST`: too many consecutive frames had no valid measurement.
- `disabled`: no Kalman config was supplied.

## Predict-Only Mode

Predict-only happens when:

- PnP returns no pose for the frame.
- The measurement contains invalid numeric values.
- The raw PnP reprojection error is larger than:

```yaml
max_reprojection_error_px: 8.0
```

The filter can bridge short gaps. If the number of consecutive missing frames exceeds:

```yaml
max_missing_frames: 10
```

the filter reports `LOST`. A later valid measurement can correct the state again.

## Tuning Q And R

Process noise `Q` controls how freely the filter can move between frames.

Increase these if the filtered pose lags behind fast motion:

```yaml
position_process_noise: 0.01
velocity_process_noise: 0.1
rotation_process_noise: 0.01
angular_velocity_process_noise: 0.1
```

Decrease them if the filtered pose jitters too much when detections are stable.

Measurement noise `R` controls how much the filter trusts raw PnP measurements.

Increase these if raw PnP is noisy:

```yaml
position_measurement_noise: 0.005
rotation_measurement_noise: 0.02
```

Decrease them if raw PnP is reliable and the filter feels too sluggish.

## Limitations

This is a fixed linear Kalman baseline. It is intentionally simple.

- It uses a Rodrigues rotation vector, not a quaternion manifold filter.
- It does not use keypoint reliability or dynamic measurement noise.
- It does not yet adjust noise from reprojection error beyond gating.
- It is best suited for replay smoke tests and first-pass smoothing checks.
- Reliability-aware dynamic KF should be implemented later as a separate stage.
## Code Reading Notes

- 先读 `src/yolo6d_car/tracking/pose_kalman_filter.py`，理解 12D state 和 6D measurement。
- 再读 `src/yolo6d_car/pipeline.py` 中 Kalman 相关字段，理解 raw pose 如何进入 KF。
- `tracking_state=PREDICT_ONLY` 表示当前帧没有使用 measurement，只做预测。
- `tracking_state=LOST` 表示连续缺失帧超过 `max_missing_frames`。

常见错误：

- 忘记传 `--kalman-config`，CSV 里就不会有 filtered pose。
- timestamp 缺失时会退回 `default_fps`，真实评估时应尽量使用真实时间戳。
