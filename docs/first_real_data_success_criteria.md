# First Real Data Success Criteria

This checklist defines what counts as a successful first real lab data run for YOLO6D_Car.

## Minimum Success

- [ ] At least one Hikrobot lens is calibrated successfully: 6mm or 8mm.
- [ ] Calibration output exists:
  - `G:\YOLO6D_Car_Data\outputs\calibration\hik_6mm\camera_intrinsics_hik_6mm.yaml`, or
  - `G:\YOLO6D_Car_Data\outputs\calibration\hik_8mm\camera_intrinsics_hik_8mm.yaml`
- [ ] At least 3 real capture sessions are completed.
- [ ] Each completed session has:
  - `images\`
  - `capture_metadata.json`
  - `capture_index.csv`
  - matching FzMotion CSV under `G:\YOLO6D_Car_Data\FZmotion_Data\raw_csv`
- [ ] `scripts/check_capture_quality.py` result is `PASS` or `WARNING` for each usable session.
- [ ] `scripts/check_mocap_csv.py` result is `PASS` or `WARNING` for each usable mocap CSV.
- [ ] Mocap-assisted labels can be generated for at least one session.
- [ ] `scripts/visualize_auto_labels.py` overlays look correct by visual inspection.
- [ ] A YOLO Pose `dataset.yaml` can be generated.
- [ ] A small training command can be printed, or one tiny training smoke run can be started intentionally.
- [ ] A replay config can be generated for at least one real session.
- [ ] One real session can run replay.
- [ ] Raw / fixed KF / reliability-aware KF ablation can run on one real session.

## Strong Success

- [ ] Both 6mm and 8mm Hikrobot lenses are calibrated.
- [ ] At least these 3 session types are usable:
  - static
  - slow lateral
  - fast lateral
- [ ] At least one train split and one test split session are available.
- [ ] Label visualization shows all or most 12 keypoints in plausible positions.
- [ ] PnP pose is numerically stable for a short real replay.
- [ ] Fixed KF and reliability-aware KF produce CSV outputs with filtered pose columns.
- [ ] `scripts/evaluate_pose_results.py` can compare raw vs filtered smoothness.

## Not Required on First Day

- Full-scale YOLO Pose training.
- Final paper-quality ablation.
- Learned uncertainty or advanced dynamic filtering.
- Perfect calibration for both lenses.
- Perfect labels for every session.

## Stop Conditions

Pause data collection and fix the issue if:

- Calibration reprojection error is clearly high or unstable.
- Camera/lens configuration is mixed, for example 6mm captures use 8mm intrinsics.
- FzMotion rigid body names do not match the manifest.
- Capture images are blurry or repeated.
- Label overlays are visibly shifted, mirrored, or scaled incorrectly.
- Session metadata is missing.
