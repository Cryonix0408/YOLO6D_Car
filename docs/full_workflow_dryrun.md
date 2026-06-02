# Full Workflow Dry-Run

`scripts\dryrun_full_workflow.py` is a pre-lab checklist runner. It verifies
that the project wiring is coherent before real camera capture, mocap labeling,
training, replay, and ablation.

## What It Does Not Do

It does not:

- capture from RealSense or Hikrobot cameras,
- connect to mocap hardware,
- train a YOLO model,
- run large ablations,
- create large datasets,
- modify Kalman logic.

## What It Checks

It checks:

- Python/import/path readiness,
- `configs\paths_local.yaml`,
- session manifest structure and planned data paths,
- dataset manifest structure and planned dataset paths,
- model registry structure and planned model paths,
- generated commands for replay, Kalman, ablation, training, and archiving,
- optional replay smoke tests,
- optional smoke ablation.

## Basic Dry-Run

```powershell
D:\Envs\yolo6d\python.exe scripts\dryrun_full_workflow.py ^
  --paths-config configs\paths_local.yaml ^
  --session-manifest configs\session_manifest_template.yaml ^
  --dataset-manifest configs\dataset_manifest_template.yaml ^
  --model-registry configs\model_registry_template.yaml ^
  --model-id car_pose_12pts_v1_yolov8n_pose ^
  --run-name full_workflow_dryrun ^
  --output-dir results\workflow_dryruns\full_workflow_dryrun
```

With `--paths-config`, the output directory resolves under:

```text
G:\YOLO6D_Car_Data\results\workflow_dryruns\full_workflow_dryrun
```

## Dry-Run With Smoke Tests

```powershell
D:\Envs\yolo6d\python.exe scripts\dryrun_full_workflow.py ^
  --paths-config configs\paths_local.yaml ^
  --session-manifest configs\session_manifest_template.yaml ^
  --dataset-manifest configs\dataset_manifest_template.yaml ^
  --model-registry configs\model_registry_template.yaml ^
  --model-id car_pose_12pts_v1_yolov8n_pose ^
  --run-name full_workflow_dryrun_smoke ^
  --execute-smoke-tests ^
  --execute-ablation-smoke ^
  --output-dir results\workflow_dryruns\full_workflow_dryrun_smoke
```

## Output Files

The output directory contains:

```text
workflow_readiness_summary.json
workflow_readiness_summary.csv
workflow_dryrun_report.md
generated_commands.md
```

`workflow_dryrun_report.md` is the human-readable report. It includes:

- environment summary,
- D/G-drive path summary,
- manifest summaries,
- Ready / Missing / Placeholder table,
- next real capture checklist.

`generated_commands.md` is the command sheet for the next stages.

## Reading the Report

Statuses mean:

- `Ready`: code/config wiring exists and validates.
- `Missing data expected`: real captures, mocap CSV, labels, or weights are not
  present yet, which is normal before lab work.
- `Placeholder`: entry exists, but full algorithmic implementation is reserved.
- `Pending`: requires hardware, real data, or actual training.
- `Passed` / `Failed`: an optional smoke command was executed.

## Back in the Lab

Start with:

1. create a real `session_id`,
2. confirm camera intrinsics,
3. confirm mocap rigid body names,
4. capture images/videos,
5. sync captures to G drive,
6. place FzMotion CSV under `FZmotion_Data`,
7. update the session manifest,
8. generate mocap labels,
9. prepare the dataset,
10. train YOLO Pose,
11. archive `best.pt`,
12. run replay, ablation, and evaluation.
## Code Reading Notes

- 入口脚本是 `scripts/dryrun_full_workflow.py`。
- 它用于检查工程连贯性，不采集、不训练、不生成大数据。
- 如果某些 G 盘真实数据缺失，模板/planned 状态下通常应记录为 expected missing，而不是工程失败。
