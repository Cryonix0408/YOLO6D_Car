# Build First, Then Execute Plan

The current strategy is to finish the program skeleton first, then collect real data, calibrate, train, and run experiments.

## Stage 0: 环境和路径

Goal: make Python, CUDA, repo root, and G-drive data root predictable.

Status: mostly built.

Key command:

```powershell
D:\Envs\yolo6d\python.exe scripts\check_project_readiness.py --paths-config configs\paths_local.yaml
```

## Stage 1: 相机标定程序构建

Goal: separately calibrate Hik MV-CS016-10UC with 6mm and 8mm lenses.

Status: baseline built for chessboard calibration.

Next execution: print board, capture 30-80 diverse samples for each lens, inspect reprojection reports.

## Stage 2: 数据同步程序构建

Goal: copy laptop capture sessions to workstation G-drive data root.

Status: built with dry-run, incremental copy, overwrite option, size verification, and logs.

Next execution: test laptop `Z:\captures` mapping with one small real session.

## Stage 3: 采集程序构建

Goal: collect D455 object/board samples with metadata.

Status: built.

Next execution: verify capture folder structure and timestamps on a short session.

## Stage 4: 自动标签程序构建

Goal: combine images, FzMotion CSV, camera/object rigid transforms, and object model to produce YOLO Pose labels.

Status: built.

Next execution: label one small session and inspect overlays before batch labeling.

## Stage 5: 数据集构建程序

Goal: merge auto-label sessions into an Ultralytics Pose dataset.

Status: built.

Next execution: build one dataset, inspect `dataset.yaml`, image/label counts, and split summary.

## Stage 6: 训练程序

Goal: train Ultralytics YOLO Pose and store runs on G drive.

Status: training wrapper built.

Next execution: train a short sanity run first, then full run after labels look correct.

## Stage 7: replay / realtime 程序

Goal: replay should validate PnP logic without hardware; realtime should run with camera and trained weights.

Status: replay smoke works; live entry exists.

Next execution: after training, run live with matching camera intrinsics and model weights.

## Stage 8: fixed Kalman Filter

Goal: add a simple post-PnP smoothing baseline.

Status: fixed 12D constant-velocity KF integrated for replay via `--kalman-config`.

Next execution: compare raw vs filtered replay CSV when real replay data exists.

## Stage 9: reliability-aware Kalman Filter

Goal: use keypoint reliability, reprojection error, and detection quality to adapt measurement noise.

Status: placeholder only.

Next build step: design reliability signals and dynamic R update after fixed KF baseline is evaluated.

## Stage 10: evaluation and paper results

Goal: produce quantitative pose metrics and experiment figures.

Status: placeholder metrics exist; full mocap comparison/report scripts are not built yet.

Next build step: add offline evaluation script after prediction logs and mocap GT format are stable.
## Code Reading Notes

这个项目采用“先构建工程入口，再采真实数据”的策略。阅读时不要把 placeholder 当成失败：

- placeholder 表示接口位置已经预留。
- validate-config 表示可以离线检查配置和依赖。
- 真正的性能结论必须等真实 captures、FzMotion CSV、标定和训练权重回来后再判断。

