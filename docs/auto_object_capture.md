# Auto Object Capture

This script helps one person collect small-car images without pressing a save
key for every sample. You move or place the car; the program saves only when
the view is clear, stable, and sufficiently different from the last saved
sample.

## Why Auto Capture

Manual capture is awkward when one person must move the car, check framing, and
press a key. Auto capture makes the computer wait for a good moment and reduces
duplicate images from the same pose.

## How To Collect Alone

1. Start the script.
2. Move or place the car in a new pose.
3. Hold still for a short moment.
4. Wait for the script to auto-save.
5. Move the car again.

The `s` key still force-saves the current frame, but it is only a backup.

## Auto-Save Logic

Each frame is checked for:

- blur score above `capture.blur_threshold`,
- enough time since the last save,
- stable image over `stable_frames_required` frames,
- enough difference from the last saved image,
- not paused,
- target sample count not reached.

Reject reasons include:

- `blur_too_low`
- `too_soon`
- `not_stable`
- `too_similar_to_last_saved`
- `paused`
- `target_reached`

## Duplicate Prevention

After one sample is saved, the script enters `waiting_for_scene_change`.
It will not save again until the current frame differs enough from the last
saved frame. This prevents many copies of the same car pose.

## Key Settings

- `target_samples`: total number of desired images.
- `blur_threshold`: increase if blurry images are being saved; decrease if the
  script never saves in dim lighting.
- `min_time_between_samples_s`: increase if saving is too frequent.
- `stable_frames_required`: increase if frames are saved while your hand is
  still moving.
- `frame_difference_threshold` and `min_scene_change_score`: increase if
  duplicate poses are saved; decrease if new poses are not accepted.

## Validate Config

```powershell
D:\Envs\yolo6d\python.exe scripts\capture_object_samples.py ^
  --config configs\object_capture_auto.yaml ^
  --paths-config configs\paths_local.yaml ^
  --validate-config
```

This does not open the camera.

## Dry-Run

```powershell
D:\Envs\yolo6d\python.exe scripts\capture_object_samples.py ^
  --config configs\object_capture_auto.yaml ^
  --paths-config configs\paths_local.yaml ^
  --dry-run ^
  --max-frames 20
```

Dry-run uses synthetic frames, prints decisions, and does not save images.

## Formal Run

```powershell
D:\Envs\yolo6d\python.exe scripts\capture_object_samples.py ^
  --config configs\object_capture_auto.yaml ^
  --paths-config configs\paths_local.yaml
```

Use `--overwrite` only when you intentionally want to reuse an existing session
directory. By default, a non-empty session directory is protected.

## Output Structure

Outputs are resolved through `configs\paths_local.yaml` and go under:

```text
G:\YOLO6D_Car_Data\captures\<date>\<session_name>\
```

Structure:

```text
images\
depth\
previews\
metadata\
capture_index.csv
capture_metadata.json
capture_report.md
```

If `save_depth=false`, the `depth` directory and depth files are not written.

## After Capture

1. Sync the capture folder to the workstation if collected on a laptop.
2. Put the matching FzMotion CSV under `FZmotion_Data`.
3. Update the session manifest.
4. Run mocap label generation.
5. Build the YOLO Pose dataset.

## Troubleshooting

- Never saves: lower `blur_threshold`, lower scene-change thresholds, or hold
  the car still longer.
- Saves too often: raise `min_time_between_samples_s`,
  `frame_difference_threshold`, or `min_scene_change_score`.
- Blurry images: improve lighting, refocus, or raise `blur_threshold`.
- Camera cannot open: check RealSense Viewer or other programs are not using
  the camera; verify USB 3.0 connection.
- Output directory exists: change `session_name` or pass `--overwrite` when
  intentionally continuing that session.
## Code Reading Notes

- 核心脚本是 `scripts/capture_object_samples.py`。
- 自动保存条件主要看 blur_score、scene_change、stable_frame_count 和 waiting_for_scene_change。
- `s` 键是备用强制保存，不是主要流程。

如果一直不保存：

- 降低 `blur_threshold` 或检查对焦/光照。
- 降低 `min_scene_change_score`。
- 确认画面已经稳定达到 `stable_frames_required`。
