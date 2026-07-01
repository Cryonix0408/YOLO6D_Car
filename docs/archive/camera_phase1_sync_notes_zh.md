# 第一阶段相机架构代码同步说明

## 1. 同步方式

当前 `D:\YOLO6D_Car` 是 Git 仓库：

- 当前分支：`main`
- 远程仓库：`https://github.com/Cryonix0408/YOLO6D_Car.git`
- 主机预计项目路径：`D:\Research\YOLO6D_Car`

本次建议通过独立 Git 分支同步，不生成代码 zip。

建议分支名：

```text
codex/camera-phase1
```

建议 commit message：

```text
feat(camera): complete phase-1 unified camera architecture
```

## 2. 本同步包含什么

本次同步包含第一阶段统一相机架构相关代码、配置和中文文档：

### 代码

- `src/yolo6d_car/camera/base_camera.py`
- `src/yolo6d_car/camera/factory.py`
- `src/yolo6d_car/camera/hikvision_stream.py`
- `src/yolo6d_car/camera/webcam.py`
- `src/yolo6d_car/camera/__init__.py`
- `scripts/capture_object_samples.py`

### 配置

- `configs/cameras/`
- `configs/capture/`
- `configs/calibration/`

### 文档

- `README.md`
- `docs/camera_architecture_zh.md`
- `docs/camera_config_migration_zh.md`
- `docs/camera_phase1_acceptance_report_zh.md`
- `docs/camera_phase1_sync_notes_zh.md`

## 3. 本同步不包含什么

本次 Git 同步不包含：

- `D:\CaptureData`
- `outputs/`
- `captures/`
- `results/`
- `logs/`
- `FZmotion_Data/`
- `__pycache__/`
- `.pytest_cache/`
- 虚拟环境目录
- 图片和视频采集数据
- 模型权重和导出模型，例如 `*.pt`、`*.pth`、`*.onnx`、`*.engine`
- 大型中间文件，例如 `*.bag`、`*.npy`、`*.npz`

项目 `.gitignore` 已排除主要生成数据、缓存、模型权重和视频格式。本次提交前仍应执行 `git status`，确认没有图片、视频或本地数据被意外暂存。

## 4. 为什么不包含大数据

Git 用于同步源代码、配置和文档，不适合传输采集图片、视频、动捕 CSV、训练输出和模型权重。

大数据应继续通过共享盘、同步脚本或其他数据传输方式管理。这样可以避免 Git 仓库体积快速增长，也能降低误删、冲突和拉取失败风险。

## 5. 笔记本推荐提交流程

在笔记本执行：

```powershell
Set-Location D:\YOLO6D_Car

git status
git switch -c codex/camera-phase1

git add README.md
git add scripts/capture_object_samples.py
git add src/yolo6d_car/camera
git add configs/cameras configs/capture configs/calibration
git add docs/camera_architecture_zh.md
git add docs/camera_config_migration_zh.md
git add docs/camera_phase1_acceptance_report_zh.md
git add docs/camera_phase1_sync_notes_zh.md

git status
git diff --cached --stat
git diff --cached --check

git commit -m "feat(camera): complete phase-1 unified camera architecture"
git push -u origin codex/camera-phase1
```

不要直接执行 `git add .`，以免未来新增但未被 `.gitignore` 覆盖的数据文件被误提交。

## 6. 主机同步前需要备份什么

主机项目路径预计为 `D:\Research\YOLO6D_Car`。同步前先检查：

```powershell
Set-Location D:\Research\YOLO6D_Car
git status
git branch --show-current
git remote -v
```

如果主机工作区存在未提交修改，先提交到主机自己的备份分支：

```powershell
git switch -c backup/host-before-camera-phase1
git add -u
git commit -m "chore: backup host changes before camera phase1 sync"
```

如果主机存在不希望提交的大数据，只备份代码和配置，不要把大数据加入 Git。

建议重点检查和备份：

- `scripts/capture_object_samples.py`
- `src/yolo6d_car/camera/`
- `configs/cameras/`
- `configs/capture/`
- `configs/calibration/`
- `README.md`
- `docs/`

## 7. 主机拉取流程

主机工作区干净后执行：

```powershell
Set-Location D:\Research\YOLO6D_Car

git fetch origin
git switch codex/camera-phase1
git pull --ff-only origin codex/camera-phase1
```

验证通过后，如需合并回主机 `main`：

```powershell
git switch main
git pull --ff-only origin main
git merge --no-ff codex/camera-phase1
```

如果主机 `main` 有额外修改，不要强制覆盖；应先检查差异并解决冲突。

## 8. 主机同步后验证命令

先使用主机实际 Python 环境，不要直接假定笔记本 Python 路径可用。

```powershell
Set-Location D:\Research\YOLO6D_Car

python -m compileall src scripts

python scripts\smoke_replay_pipeline.py `
  --config configs\local_smoke_replay.yaml `
  --max-frames 3

python scripts\capture_object_samples.py `
  --config configs\capture\d455_object_capture_auto.yaml `
  --paths-config configs\paths_laptop.yaml `
  --validate-config

python scripts\capture_object_samples.py `
  --config configs\capture\hik_6mm_object_capture_auto.yaml `
  --paths-config configs\paths_laptop.yaml `
  --validate-config

python scripts\capture_object_samples.py `
  --config configs\capture\hik_8mm_object_capture_auto.yaml `
  --paths-config configs\paths_laptop.yaml `
  --validate-config
```

主机不应直接长期使用 `configs\paths_laptop.yaml`。完成代码验收后，应换成主机自己的路径配置，并重新运行配置校验。

## 9. 如何确认 D455 和 Hikrobot 配置仍然可用

### D455

1. `d455_object_capture_auto.yaml --validate-config` 无错误。
2. D455 配置仍包含 RGB、Depth 和 `align_depth_to_color` 字段。
3. 原 D455 底层实现仍存在，并由统一适配器调用。
4. 真实 D455 硬件测试需在连接相机后单独进行。

### Hikrobot 6mm

1. `hik_6mm_object_capture_auto.yaml --validate-config` 无错误。
2. 主机能访问 6mm 内参文件，或已将内参文件同步到主机数据目录。
3. 相机配置中的镜头、分辨率、曝光、增益等参数符合实际设备。
4. `white_balance` 当前只保留在配置中，统一适配器尚未显式完整应用。

### Hikrobot 8mm

1. 配置文件可以通过结构校验。
2. 当前 8mm 内参尚未标定。
3. 正式使用前必须生成独立的：

```text
camera_intrinsics_hik_8mm.yaml
```

不得复用 6mm 内参。

## 10. 真实硬件验证提醒

第一阶段当前只完成离线架构和配置验收，以下内容仍未完成真实硬件验证：

- D455 RGB、Depth、深度对齐和时间戳。
- Hikrobot 6mm/8mm 实际采集、曝光、增益、Gamma 和白平衡。
- Hikrobot 非 `off` 触发模式。
- 持续采集帧率、丢帧、保存速度和时间戳稳定性。
- Webcam 实际设备索引和采集稳定性。

完成主机代码同步不代表真实相机已经验收通过。

