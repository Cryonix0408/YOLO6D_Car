# Path Migration Audit

Date: 2026-05-30

Scope: safe audit only. No runtime files were modified. This report reviews hard-coded legacy paths and relative data/output paths that may need migration from code-on-D/data-on-repo behavior to the new workstation layout:

- Code repository: `D:/Research/YOLO6D_Car`
- Large data root: `G:/YOLO6D_Car_Data`
- Local path config: `configs/paths_local.yaml`

Search terms included legacy absolute paths, `FZmotion_Data`, `outputs/`, `best.pt`, `train_runs`, `auto_labels`, `datasets`, `calibration`, and common path keys such as `csv_path`, `model_path`, `output_dir`, and `dataset_dir`.

Raw filtered search hits: 360. Many hits were expected false positives or safe references, including `project` as a YAML key, `source_marker_id` in model definitions, `reprojection` text, and example/documentation paths. The findings below are grouped by actionable path pattern.

## Summary

| Class | Grouped findings | Runtime-affecting | Recommended action |
| --- | ---: | ---: | --- |
| A. Runtime configs that should be migrated | 14 | 14 | Migrate first or create G-drive config variants. |
| B. Runtime scripts that should support `paths_local.yaml` | 10 | 7 | Add missing `--paths-config` support where useful. |
| C. Historical docs that can stay unchanged | 7 | 0 | Leave for now; refresh examples later. |
| D. Tool scripts that can be updated later | 4 | 0 | Update only when those tools are reused. |
| E. Safe examples that should remain examples | 3 | 1 | Keep unchanged. |

## A. Runtime Configs That Should Be Migrated

| File | Line | Old or suspicious path | Safe to migrate | Recommended new form | Risk | Runtime |
| --- | ---: | --- | --- | --- | --- | --- |
| `configs/board_capture.yaml` | 16 | `D:\YOLO6D_Car\FZmotion_Data\current_rigids_recalib_20260410.csv` | Yes | Prefer relative-to-data-root `FZmotion_Data/current_rigids_recalib_20260410.csv` with `--paths-config configs/paths_local.yaml`; or absolute `G:/YOLO6D_Car_Data/FZmotion_Data/current_rigids_recalib_20260410.csv`. | High | Yes |
| `configs/board_capture.yaml` | 49 | `outputs/fzmotion_pose_log.csv` | Yes | Keep as relative-to-data-root `outputs/fzmotion_pose_log.csv` when the script is run with `--paths-config`; otherwise use `G:/YOLO6D_Car_Data/outputs/fzmotion_pose_log.csv`. | Medium | Yes |
| `configs/object_capture.yaml` | 16 | `D:\YOLO6D_Car\FZmotion_Data\Data 2026-03-26 15-52-58.csv` | Yes | Prefer relative-to-data-root `FZmotion_Data/Data 2026-03-26 15-52-58.csv` with `--paths-config`; or absolute G-drive path. | High | Yes |
| `configs/object_capture.yaml` | 51 | `outputs/fzmotion_pose_log.csv` | Yes | Relative-to-data-root `outputs/fzmotion_pose_log.csv` with `--paths-config`; or absolute G-drive path. | Medium | Yes |
| `configs/fzmotion_fixed_camera_current_rigids.yaml` | 15 | `D:\YOLO6D_Car\FZmotion_Data\current_rigids.csv` | Yes | Prefer relative-to-data-root `FZmotion_Data/current_rigids.csv` with `--paths-config`; or absolute G-drive path. | High | Yes |
| `configs/fzmotion_fixed_camera_current_rigids.yaml` | 51 | `outputs/fzmotion_pose_log.csv` | Yes | Relative-to-data-root `outputs/fzmotion_pose_log.csv` with `--paths-config`; or absolute G-drive path. | Medium | Yes |
| `configs/fzmotion_fixed_camera_live_v1.yaml` | 40 | `outputs/train_runs/uav_4m_20sessions_pose_v1/weights/best.pt` | Yes | Relative-to-data-root `outputs/train_runs/uav_4m_20sessions_pose_v1/weights/best.pt` with `--paths-config`; or absolute `G:/YOLO6D_Car_Data/outputs/train_runs/.../best.pt`. | High | Yes |
| `configs/fzmotion_fixed_camera_live_v1.yaml` | 67 | `outputs/live_pose_log_v1.csv` | Yes | Relative-to-data-root `outputs/live_pose_log_v1.csv` with `--paths-config`; or absolute G-drive path. | Medium | Yes |
| `configs/fzmotion_fast_moving_live.yaml` | 41 | `outputs/train_runs/uav_4m_20sessions_pose_v1/weights/best.pt` | Yes | Relative-to-data-root `outputs/train_runs/uav_4m_20sessions_pose_v1/weights/best.pt` with `--paths-config`; or absolute G-drive path. | High | Yes |
| `configs/fzmotion_fast_moving_live.yaml` | 71 | `outputs/fast_moving_live_pose_log.csv` | Yes | Relative-to-data-root `outputs/fast_moving_live_pose_log.csv` with `--paths-config`; or absolute G-drive path. | Medium | Yes |
| `configs/uav_4m_20_sessions.yaml` | 5 | `outputs/auto_labels/uav_4m_20sessions` | Yes | Keep as relative-to-data-root and require the batch label script to run with `--paths-config configs/paths_local.yaml`. | Medium | Yes |
| `configs/uav_4m_20_sessions.yaml` | 13-166 | Repeated `outputs/object_capture/...` and `FZmotion_Data/...` under `samples_dir` and `csv_path` | Yes | Keep relative-to-data-root if all referenced sessions are stored below `G:/YOLO6D_Car_Data`; otherwise convert individual entries to absolute G-drive paths. | Medium | Yes |

Notes:

- `configs/paths_local.yaml` intentionally contains G-drive paths and is not a migration problem.
- `configs/local_smoke_replay.yaml` must remain unchanged because it is the known passing baseline smoke test.
- A G-drive smoke config already exists and passed with `--paths-config`.

## B. Runtime Scripts That Should Support `paths_local.yaml`

| File | Line | Old or suspicious path | Safe to migrate | Recommended new form | Risk | Runtime |
| --- | ---: | --- | --- | --- | --- | --- |
| `scripts/capture_board_samples.py` | 80 | Fallback `ROOT / "outputs" / "board_capture" / timestamp` | Mostly already handled | Keep fallback for backwards compatibility; prefer `--paths-config` so output resolves under `G:/YOLO6D_Car_Data/outputs/board_capture/...`. | Low | Yes |
| `scripts/capture_object_samples.py` | 67 | Fallback `ROOT / "outputs" / "object_capture" / timestamp` | Mostly already handled | Keep fallback; prefer `--paths-config` for G-drive output. | Low | Yes |
| `scripts/generate_mocap_labels.py` | 135 | Fallback `ROOT / "outputs" / "auto_labels" / samples_dir.name` | Mostly already handled | Keep fallback; prefer `--paths-config` for G-drive output. | Low | Yes |
| `scripts/prepare_yolo_pose_dataset.py` | 79-80 | Default dataset output derived as `... / "datasets" / ...` | Mostly already handled | Keep explicit output behavior; with G-drive auto-label inputs this resolves under G-drive outputs. | Low | Yes |
| `scripts/train_ultralytics_pose.py` | 31 | Default `--project outputs/train_runs` | Mostly already handled | Keep default; when `--paths-config` is passed, route relative project paths through `outputs_root`. | Low | Yes |
| `scripts/solve_camera_rigid_to_optical.py` | 72 | Default `ROOT / "outputs" / "calibration" / "camera_rigid_to_optical.json"` | Yes | Add optional `--paths-config`; resolve default as `outputs/calibration/camera_rigid_to_optical.json` under `outputs_root`. | Medium | Yes |
| `scripts/refine_camera_rigid_to_optical_from_sessions.py` | 77 | Default `ROOT / "outputs" / "calibration" / "camera_rigid_to_optical_refined_from_sessions.json"` | Yes | Add optional `--paths-config`; resolve default under G-drive `outputs/calibration`. | Medium | Yes |
| `scripts/build_custom_model_from_csv.py` | 77 | Default `ROOT / "outputs" / "calibration" / "car_custom_keypoints_report.json"` | Yes | Add optional `--paths-config`; resolve report under G-drive `outputs/calibration`. | Medium | Yes |
| `scripts/migrate_rigid_frame_from_csv.py` | 354 | Default `ROOT / "outputs" / "calibration" / "{rigid_body}_migration_report.json"` | Yes | Add optional `--paths-config`; resolve report under G-drive `outputs/calibration`. | Medium | Yes |
| `scripts/collect_hikvision_sequence.py` | 83 | Explicit `output_dir = Path(args.output_dir).resolve()` | Leave mostly unchanged | Require users to pass an explicit G-drive output directory, for example `G:/YOLO6D_Car_Data/captures/...`. | Low | Yes |

Additional low-risk runtime references:

- `scripts/visualize_hikvision_sequence.py:61` writes preview video under the selected sequence directory. This is safe if the sequence directory is on G drive.
- `scripts/export_ultralytics_pose_to_replay.py:116` uses explicit `--mocap-csv`; no default migration is needed.
- `scripts/batch_generate_mocap_labels.py` has relative `outputs/auto_labels/batch_sessions` behavior, but this is expected to resolve through `paths_local.yaml` when provided.

## C. Historical Docs That Can Stay Unchanged

| File | Line | Old or suspicious path | Safe to migrate | Recommended new form | Risk | Runtime |
| --- | ---: | --- | --- | --- | --- | --- |
| `README.md` | 181-205 | Historical commands and paths using `outputs/`, `FZmotion_Data/`, and `best.pt` | Leave for now | Keep until the runtime YAML migration is complete, then refresh docs in one pass. | Low | No |
| `docs/setup_and_faq.md` | 49-57 | Older D-drive project/data layout examples | Leave for now | Historical setup notes can remain; optionally add cross-reference to the new workstation section later. | Low | No |
| `docs/mocap_label_generation.md` | 24-25 | Example `outputs/object_capture/...` and `FZmotion_Data/...` paths | Leave for now | Keep as examples; later update to mention `G:/YOLO6D_Car_Data`. | Low | No |
| `docs/training_guide.md` | 24-31, 55-56 | Example dataset and training output paths under `outputs/` | Leave for now | Keep as examples; later document `--paths-config` training command. | Low | No |
| `docs/handover_checklist.md` | 7, 39-43 | Historical handoff references to missing `outputs/`, `FZmotion_Data/`, datasets, and weights | Leave for now | Keep as historical checklist; future note can point to G-drive locations. | Low | No |
| `docs/project_guide.md` | 133-135 | Example label/dataset output commands using `outputs/` | Leave for now | Keep until migration commands are finalized. | Low | No |
| `docs/live_inference.md` | 30 | Example `outputs/train_runs/.../best.pt` path | Leave for now | Later update after live inference config migration. | Low | No |

## D. Tool Scripts That Can Be Updated Later

| File | Line | Old or suspicious path | Safe to migrate | Recommended new form | Risk | Runtime |
| --- | ---: | --- | --- | --- | --- | --- |
| `tools/enhance_ppt_v2.ps1` | 3-4 | `D:\YOLO6D_Car\outputs\lecture_handout_work\...` | Yes | Convert to `G:/YOLO6D_Car_Data/outputs/lecture_handout_work/...` or parameterize input/output paths. | Medium | No |
| `tools/build_experiment_data_checklist.py` | 8 | `D:\YOLO6D_Car\outputs\lecture_handout_work\实验数据清单_整理版.docx` | Yes | Parameterize or route through G-drive outputs. | Medium | No |
| `tools/build_existing_experiment_data_report.py` | 19, 22-28, 553, 669, 713 | `ROOT / "outputs" / ...` report/data paths | Yes | Add optional path config or output-root argument before reusing this report generator. | Low | No |
| `tools/prepare_ppt_v2_assets.py` | 13 | `ROOT / "outputs" / "lecture_handout_work" / "ppt_v2_assets"` | Yes | Add output-root argument or use G-drive outputs for generated assets. | Low | No |

## E. Safe Examples That Should Remain Examples

| File | Line | Old or suspicious path | Safe to migrate | Recommended new form | Risk | Runtime |
| --- | ---: | --- | --- | --- | --- | --- |
| `configs/local_smoke_replay.yaml` | multiple | Blank `csv_path`, null `save_csv`, and repo-local example paths | Leave unchanged | This config is the passing baseline smoke test and should keep using `data/examples`. | Low | Yes |
| `configs/local_smoke_replay_gdrive.yaml` | multiple | G-drive aware smoke config with blank optional CSV/log fields | Leave unchanged | Continue using with `--paths-config configs/paths_local.yaml`. | Low | Yes |
| `models/*.json` | multiple | `source_marker_id` and other `source` false positives | Leave unchanged | These are model metadata fields, not filesystem paths. | Low | No |

## Top 10 Migration Priorities

1. `configs/board_capture.yaml:16` old absolute `D:\YOLO6D_Car\FZmotion_Data\...` CSV path.
2. `configs/object_capture.yaml:16` old absolute `D:\YOLO6D_Car\FZmotion_Data\...` CSV path.
3. `configs/fzmotion_fixed_camera_current_rigids.yaml:15` old absolute `current_rigids.csv` path.
4. `configs/fzmotion_fixed_camera_live_v1.yaml:40` model weight path `outputs/train_runs/.../best.pt`.
6. `configs/fzmotion_fast_moving_live.yaml:41` model weight path `outputs/train_runs/.../best.pt`.
7. `configs/uav_4m_20_sessions.yaml:13-166` repeated batch session `samples_dir` and `csv_path` entries.
8. `configs/*capture*.yaml` and `configs/fzmotion*.yaml` `save_csv: outputs/...` log paths.
9. Calibration/default report writers in `scripts/solve_camera_rigid_to_optical.py`, `scripts/refine_camera_rigid_to_optical_from_sessions.py`, `scripts/build_custom_model_from_csv.py`, and `scripts/migrate_rigid_frame_from_csv.py`.
10. Legacy absolute D-drive paths in presentation/report tools under `tools/`.

## Recommended Next Patch Plan

1. Migrate runtime YAML configs first. Replace old absolute `D:\YOLO6D_Car\FZmotion_Data\...` entries with relative-to-data-root paths such as `FZmotion_Data/current_rigids.csv`, or create separate G-drive config variants if the old files must remain as historical snapshots.
2. Confirm all runtime commands that use migrated YAMLs pass `--paths-config configs/paths_local.yaml`.
3. Add `--paths-config` support to the calibration and model-building scripts that still default to repo-local `outputs/calibration`.
4. Update live inference docs and commands after the model weight location on G drive is confirmed.
5. Leave historical docs and presentation/report tools unchanged until those workflows are actively reused.
6. Add a small path-resolution smoke check that loads key YAMLs with `configs/paths_local.yaml` and verifies generated output/model paths resolve under `G:/YOLO6D_Car_Data`.

