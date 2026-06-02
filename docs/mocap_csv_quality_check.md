# Mocap CSV Quality Check

`scripts\check_mocap_csv.py` checks whether a FzMotion or generic mocap CSV is
usable for automatic labeling and replay.

## Supported Formats

Generic pose CSV:

```text
timestamp,rigid_body,tx,ty,tz,qx,qy,qz,qw
```

FzMotion CSV:

- first row starts with `DataName`,
- rigid body columns are described by the multi-row FzMotion header,
- `LengthUnits` is converted to meters.

If the format is not recognized, the script reports a clear error and includes
a header preview.

## Validate Config

```powershell
D:\Envs\yolo6d\python.exe scripts\check_mocap_csv.py ^
  --csv-path FZmotion_Data\raw_csv\2026-05-30_car_static_001.csv ^
  --paths-config configs\paths_local.yaml ^
  --camera-rigid d455_rigid ^
  --object-rigid car_rigid ^
  --output-dir results\mocap_quality\2026-05-30_car_static_001 ^
  --validate-config
```

This resolves paths and previews the format if the file exists.

## Full Check

```powershell
D:\Envs\yolo6d\python.exe scripts\check_mocap_csv.py ^
  --csv-path FZmotion_Data\raw_csv\2026-05-30_car_static_001.csv ^
  --paths-config configs\paths_local.yaml ^
  --camera-rigid d455_rigid ^
  --object-rigid car_rigid ^
  --output-dir results\mocap_quality\2026-05-30_car_static_001 ^
  --plot
```

Relative `FZmotion_Data/...` and `results/...` paths resolve under
`G:\YOLO6D_Car_Data` when `--paths-config configs\paths_local.yaml` is used.

## Outputs

```text
mocap_summary.json
mocap_summary.csv
mocap_quality_report.md
rigid_body_list.txt
timestamp_distribution.png
position_trajectory_preview.png
```

Plots are skipped with a warning if matplotlib is unavailable.

## What It Checks

- file exists and file size,
- row/frame count,
- timestamp range and frequency estimate,
- empty/NaN/invalid numeric cells,
- rigid body names,
- expected camera and object rigid bodies,
- valid frame count per rigid body,
- adjacent-frame position and rotation jumps,
- CSV read time.

## Interpreting Results

- `PASS`: expected rigid bodies are present and no major quality issue was found.
- `WARNING`: usable but has NaN/empty cells or pose jump anomalies.
- `FAIL`: missing required rigid body or unreadable/unrecognized CSV.

If the camera or object rigid body is missing, fix the rigid-body names in the
session manifest or export the correct bodies from FzMotion.
