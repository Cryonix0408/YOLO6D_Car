# Hik Camera Calibration

This project uses the Hikrobot MV-CS016-10UC industrial camera with two lenses:

- 6mm lens
- 8mm lens

Each lens must be calibrated separately because focal length, principal point, distortion, focus, and mounting can change when the lens changes. Do not reuse 6mm intrinsics for the 8mm lens, or 8mm intrinsics for the 6mm lens.

## Output Layout

Calibration outputs are stored under the G-drive data root:

```text
G:\YOLO6D_Car_Data\outputs\calibration
```

6mm output:

```text
G:\YOLO6D_Car_Data\outputs\calibration\hik_6mm
├── raw_images
├── debug_corners
├── samples
├── undistort_check
├── camera_intrinsics_hik_6mm.yaml
├── calibration_report_hik_6mm.md
└── calibration_summary.json
```

8mm output:

```text
G:\YOLO6D_Car_Data\outputs\calibration\hik_8mm
├── raw_images
├── debug_corners
├── samples
├── undistort_check
├── camera_intrinsics_hik_8mm.yaml
├── calibration_report_hik_8mm.md
└── calibration_summary.json
```

If a session already exists and `--overwrite` is not passed, capture mode creates a timestamped session such as:

```text
hik_6mm_20260530_153000
```

## Calibration Board

The first baseline supports a chessboard:

```yaml
calibration_board:
  type: "chessboard"
  pattern_cols: 9
  pattern_rows: 6
  square_size_mm: 25.0
```

`pattern_cols` and `pattern_rows` are the number of inner corners, not the number of printed squares.

## Board Placement Advice

Use a flat, rigid board. Keep the printed square size accurate. Make sure the lens is tightened and focus does not change during capture.

Recommended views:

- Center
- Left top
- Right top
- Left bottom
- Right bottom
- Near distance
- Far distance
- Tilted forward/backward
- Rotated clockwise/counterclockwise

Recommended sample count: 30-80 accepted images.

## Run 6mm Calibration

Validate config without opening the camera:

```powershell
D:\Envs\yolo6d\python.exe scripts\calibrate_hik_camera.py --config configs\calibration_hik_6mm.yaml --paths-config configs\paths_local.yaml --mode validate_config
```

Capture and calibrate:

```powershell
D:\Envs\yolo6d\python.exe scripts\calibrate_hik_camera.py --config configs\calibration_hik_6mm.yaml --paths-config configs\paths_local.yaml --mode capture_and_calibrate
```

Capture only:

```powershell
D:\Envs\yolo6d\python.exe scripts\calibrate_hik_camera.py --config configs\calibration_hik_6mm.yaml --paths-config configs\paths_local.yaml --mode capture
```

Calibrate from existing samples:

```powershell
D:\Envs\yolo6d\python.exe scripts\calibrate_hik_camera.py --config configs\calibration_hik_6mm.yaml --paths-config configs\paths_local.yaml --mode calibrate
```

## Run 8mm Calibration

Validate config:

```powershell
D:\Envs\yolo6d\python.exe scripts\calibrate_hik_camera.py --config configs\calibration_hik_8mm.yaml --paths-config configs\paths_local.yaml --mode validate_config
```

Capture and calibrate:

```powershell
D:\Envs\yolo6d\python.exe scripts\calibrate_hik_camera.py --config configs\calibration_hik_8mm.yaml --paths-config configs\paths_local.yaml --mode capture_and_calibrate
```

## Automatic Sampling Behavior

The calibration program is designed for automatic sampling. You start the program, move the chessboard in front of the camera, and the program saves only useful frames.

Every frame is checked for:

- Full chessboard detection.
- Blur score above `capture.blur_threshold`.
- Corner coverage above `capture.min_corner_coverage_ratio`.
- Enough time since the last saved sample.
- Enough difference from previous saved samples.

Similarity rejection uses board center movement, board area/scale change, and overall corner distribution change. If the current view is too close to previous samples, the reject reason is:

```text
too similar to previous samples
```

After `min_samples` is reached, the program starts an automatic calibration countdown. If you keep moving the board and new useful samples are saved, the countdown is pushed back so more diverse samples can be collected. At `max_samples`, capture stops and calibration starts.

## Live Capture Window

The capture window shows:

- Current lens
- Accepted sample count
- Blur score
- Board detected/not detected
- Accept/reject reason

Keys:

- `q` or `Esc`: quit
- `s`: force-save the next detected frame as a backup override
- `c`: stop capture and calibrate after minimum samples
- `r`: reset sample diversity memory for the current run

## Checking Reprojection Error

Open the report:

```powershell
notepad G:\YOLO6D_Car_Data\outputs\calibration\hik_6mm\calibration_report_hik_6mm.md
```

Lower reprojection error is better. If RMS or mean error is high, likely causes include:

- Calibration board square size is wrong.
- Corner detection is unstable.
- Images are blurry.
- Sample poses are not diverse enough.
- Lens is loose or focus changed during capture.
- 6mm and 8mm configs or sample images were mixed.

Also inspect:

```text
debug_corners
undistort_check
```

## Using Intrinsics In PnP / Replay / Realtime

Use the intrinsics file matching the physical lens mounted on the camera:

```text
G:\YOLO6D_Car_Data\outputs\calibration\hik_6mm\camera_intrinsics_hik_6mm.yaml
G:\YOLO6D_Car_Data\outputs\calibration\hik_8mm\camera_intrinsics_hik_8mm.yaml
```

When replay or realtime configs gain a camera-intrinsics field, point them to the matching file. Until then, use the YAML values to populate camera matrix and distortion fields in the relevant PnP input path.

Do not commit raw calibration images or generated outputs. `outputs/` is ignored by `.gitignore`.

## Troubleshooting

Camera does not open:

- Check USB connection and power.
- Close other camera software.
- Install or configure Hikrobot SDK.
- Try OpenCV fallback with a different `camera.device_index` in the YAML if needed.

No board detected:

- Confirm `pattern_cols` and `pattern_rows` are inner corners.
- Improve lighting.
- Keep the whole board visible.
- Reduce motion blur.

Images rejected as blurry:

- Increase lighting or exposure.
- Stabilize the board.
- Refocus the lens.

Board coverage too small:

- Move the board closer.
- Use views where the board spans more of the image.

View too similar:

- Move the board to different image regions.
- Change distance.
- Tilt and rotate the board.
## Code Reading Notes

- CLI 入口是 `scripts/calibrate_hik_camera.py`。
- 棋盘格检测在 `src/yolo6d_car/calibration/board_detector.py`。
- 自动采样质量判断在 `calibration_quality.py`。
- OpenCV 标定求解在 `camera_calibrator.py`。

关键提醒：

- 6mm 和 8mm 必须分别标定。
- `pattern_cols` / `pattern_rows` 是内角点数量。
- reprojection error 偏高时，优先检查棋盘尺寸、清晰度、姿态覆盖和镜头是否松动。
