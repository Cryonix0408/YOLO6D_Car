# Process Single Session

`scripts/process_single_session.py` is a lightweight orchestrator for one capture session. It connects the existing session manifest, capture quality check, mocap CSV check, mocap label generation, label visualization, and replay-config generation steps.

It does not train a model and does not run ablation.

## Dry Run First

Dry-run mode validates the manifest entry, resolves paths, writes a process report, and records the commands that would be run. It does not execute data-processing steps.

```powershell
D:\Envs\yolo6d\python.exe scripts\process_single_session.py `
  --session-id 2026-05-30_car_static_001 `
  --manifest configs\session_manifest_template.yaml `
  --paths-config configs\paths_local.yaml `
  --output-dir results\session_processing\2026-05-30_car_static_001 `
  --dry-run
```

With `configs\paths_local.yaml`, the relative `results\...` output directory resolves to:

```text
G:\YOLO6D_Car_Data\results\session_processing\2026-05-30_car_static_001
```

## Formal Run

After capture images and mocap CSV are present, run without `--dry-run`:

```powershell
D:\Envs\yolo6d\python.exe scripts\process_single_session.py `
  --session-id 2026-05-30_car_static_001 `
  --manifest configs\session_manifest_template.yaml `
  --paths-config configs\paths_local.yaml `
  --output-dir results\session_processing\2026-05-30_car_static_001
```

The script stops at the first failed step and records stdout/stderr in `process_summary.json`.

## Steps

1. Validate the session manifest with `scripts/manage_sessions.py --action validate`.
2. Check capture quality with `scripts/check_capture_quality.py`.
3. Check mocap CSV quality with `scripts/check_mocap_csv.py`.
4. Generate mocap-assisted labels with `scripts/generate_mocap_labels.py`.
5. Visualize labels with `scripts/visualize_auto_labels.py`.
6. Generate one replay config from the session manifest.

If `mocap.enabled` is false, mocap-dependent steps are skipped with a recorded reason.

## Outputs

```text
results\session_processing\<session_id>\
├── process_summary.json
├── process_report.md
├── generated_commands.md
├── capture_quality\
├── mocap_quality\
└── label_visualization\
```

## Important Notes

- The script does not train YOLO Pose.
- The script does not run Kalman ablation.
- The script does not modify source images, labels, or mocap CSV files.
- The generated label command currently uses the session `camera.intrinsics` field as the `generate_mocap_labels.py --config` value. If a real session needs a separate labeling project YAML, update the manifest convention before formal processing.
- Replay config generation writes the session `outputs.replay_config` path only during a formal run.

## Troubleshooting

- Capture quality fails: check `capture.root`, `images_dir`, and `capture_index.csv`.
- Mocap CSV fails: check `mocap.csv_path`, `camera_rigid`, and `object_rigid`.
- Label generation fails: check that the label config is a full project YAML accepted by `generate_mocap_labels.py`.
- Label visualization fails: check that `outputs.auto_labels` contains `labels_yolo_pose/*.txt` and that image stems match label stems.
## Code Reading Notes

- 入口脚本是 `scripts/process_single_session.py`。
- 它是胶水层，不实现新算法，只按顺序调用已有脚本。
- `--dry-run` 是回实验室前最安全的检查方式。
- 正式运行会在某一步失败时停止，并把 stdout/stderr 写入 `process_summary.json`。
