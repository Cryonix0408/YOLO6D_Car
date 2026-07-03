# YOLO6D_Car 工程文件结构规约

本文档是给 Codex 和后续 AI agent 使用的项目工程规范。以后所有新增文件、修改文件、配置变更、脚本新增、文档新增，都必须遵守这个规约，避免项目再次冗余和混乱。

## 1. 项目背景

`YOLO6D_Car` 是一个面向 Fast-moving Object Tracking and 6DoF Pose Estimation 的项目，目标是在小车高速运动、相机可能移动、画面质量受限的条件下，稳定估计目标 6DoF 位姿。

当前核心流程包括：

- `D455` / `Hikrobot` 图像采集。
- `FzMotion` / `Mocap` 真值记录。
- `YOLO Pose` 12 点关键点检测。
- `PnP` 6DoF 位姿恢复。
- fixed Kalman Filter。
- reliability-aware Kalman Filter。
- replay。
- ablation。
- evaluation。

## 2. 总原则

- 不要随意在项目根目录新增文件。
- 不要把代码、配置、文档、数据混放。
- 不要硬编码主机或笔记本路径。
- 不要把真实采集数据、图片、视频、模型权重、输出结果加入 Git。
- 不要轻易移动已经验证过的核心脚本。
- 不要删除 legacy 文件，除非用户明确批准。
- 新增文件前必须判断它属于源码、脚本、配置、文档、数据、实验输出还是临时工具。
- 所有新功能必须说明新增了什么、放在哪里、如何验证、是否影响旧命令。

## 3. 路径规则

项目代码路径：

- 主机：`D:\Research\YOLO6D_Car`
- 笔记本：`D:\YOLO6D_Car`

数据路径：

- 主机：`G:\YOLO6D_Car_Data`
- 笔记本：`D:\CaptureData`

必须通过 paths config 管理数据根目录：

- 主机使用 `configs\paths_local.yaml`
- 笔记本使用 `configs\paths_laptop.yaml`

禁止在代码中硬编码：

- `G:\YOLO6D_Car_Data`
- `D:\CaptureData`
- `D:\Research\YOLO6D_Car`
- `D:\YOLO6D_Car`

涉及数据路径时，配置中优先使用相对 `data_root` 的路径。

## 4. 源码目录规则

新增源码应该放在：

```text
src/yolo6d_car/
```

并按模块归类：

- `camera/`：相机抽象、D455、Hikrobot、Webcam 等相机后端。
- `calibration/`：相机内参、外参、标定板检测、标定质量评估。
- `mocap/`：FzMotion / Mocap CSV 读取、时间戳匹配、刚体位姿查询。
- `labeling/`：自动标签生成相关模块；如果暂时不存在，应优先考虑新建该模块，而不是把逻辑堆进脚本。
- `dataset/`：数据集构建、拆分和格式转换；如果暂时不存在，应避免把数据集逻辑继续分散。
- `pose/`：PnP、YOLO6D 接口、位姿相关工具。
- `tracking/`：Kalman、gating、可靠性估计、状态机。
- `evaluation/`：Mocap GT 对比、指标计算、结果报告。
- `image_processing/`：色彩校正、图像增强、预处理实验。
- `management/`：session / dataset / model 管理；如果暂时不存在，可作为后续整理方向。
- `utils/`：通用工具；只有跨模块复用的工具才放这里。

短期不要移动这些核心兼容文件：

- `src/yolo6d_car/path_utils.py`
- `src/yolo6d_car/config.py`
- `src/yolo6d_car/pipeline.py`
- `src/yolo6d_car/session_manifest.py`
- `src/yolo6d_car/dataset_manifest.py`
- `src/yolo6d_car/model_registry.py`

## 5. 脚本目录规则

当前阶段核心脚本暂时保留在 `scripts/` 根目录，短期不要移动。

明确不要移动以下核心脚本：

- `scripts/capture_object_samples.py`
- `scripts/generate_mocap_labels.py`
- `scripts/solve_camera_rigid_to_optical.py`
- `scripts/verify_camera_rigid_to_optical.py`
- `scripts/calibrate_hik_camera.py`
- `scripts/prepare_yolo_pose_dataset.py`
- `scripts/train_ultralytics_pose.py`
- `scripts/run_live_pose.py`
- `scripts/smoke_replay_pipeline.py`
- `scripts/run_kalman_ablation.py`
- `scripts/evaluate_pose_results.py`

新增实验性脚本优先放：

```text
scripts/dev/
```

正式脚本命名使用：

```text
动词_对象_用途.py
```

例如：

- `check_capture_quality.py`
- `generate_mocap_labels.py`
- `prepare_yolo_pose_dataset.py`
- `run_kalman_ablation.py`

## 6. 配置目录规则

新增配置不要继续堆到 `configs/` 根目录。

推荐目录：

- `configs/cameras/`：相机类型、镜头、分辨率、曝光、增益、白平衡、触发模式等相机硬件配置。
- `configs/capture/`：采集任务配置，例如 D455 / Hikrobot 静态采集、连续采集、fast moving 采集。
- `configs/calibration/`：内参、外参、标定板参数和标定流程配置。
- `configs/labeling/`：自动标签生成、Mocap CSV 匹配、关键点投影等配置。
- `configs/tracking/`：Kalman、gating、reliability-aware 参数配置。
- `configs/replay/`：离线 replay、PnP 回放、调试输入输出配置。
- `configs/evaluation/`：GT evaluation、指标计算、报告输出配置。
- `configs/sessions/`：session 清单和采集计划配置。
- `configs/datasets/`：数据集构建、拆分和版本配置。
- `configs/models/`：模型注册、权重路径、模型版本配置。
- `configs/color_correction/`：HSV / RGB / Gamma / 白平衡等色彩校正实验配置。

旧配置暂时保留，不要删除。新文档中必须标注推荐配置入口。

## 7. 文档目录规则

文档放在 `docs/`。

推荐分类：

- `docs/index.md`
- `docs/architecture/`
- `docs/setup/`
- `docs/cameras/`
- `docs/calibration/`
- `docs/capture/`
- `docs/labeling/`
- `docs/training/`
- `docs/evaluation/`
- `docs/experiments/`
- `docs/literature/`
- `docs/archive/`
- `docs/logs/`

新增重要文档后，必须更新 `docs/index.md`。

`README.md` 只作为总入口，不要把所有细节堆到 README。

## 8. 数据与输出规则

真实数据不要放进 Git。

真实采集数据应该放：

- 主机：`G:\YOLO6D_Car_Data`
- 笔记本：`D:\CaptureData`

仓库内只允许保留少量小样例：

```text
data/examples/
```

禁止提交：

- `outputs/`
- `results/`
- `logs/`
- `FZmotion_Data/`
- `captures/`
- `*.jpg`
- `*.jpeg`
- `*.png`
- `*.bmp`
- `*.mp4`
- `*.avi`
- `*.pt`
- `*.onnx`
- `*.npy`
- `*.npz`

每次提交前必须运行：

```powershell
git status --short
```

## 9. 新增功能必须配套的内容

每次新增功能，至少要包含：

- 源码或脚本。
- 配置模板。
- 中文文档。
- dry-run 或 validate 命令。
- 不连接硬件的离线验证。
- 是否需要真实硬件验证的说明。
- `git status` 检查。

例如新增色彩校正功能时，应该包含：

- `src/yolo6d_car/image_processing/color_correction.py`
- `scripts/test_color_correction.py`
- `configs/color_correction/rgb_wall_reference.yaml`
- `docs/experiments/color_correction_zh.md`

并明确说明当前是否接入正式 pipeline。

## 10. 修改已有文件前的检查

修改前必须回答：

- 这个文件是否是核心入口？
- 是否有 README 或 docs 正在引用它？
- 是否会影响主机和笔记本两套路径？
- 是否会破坏旧命令？
- 是否需要真实硬件验证？
- 是否有 smoke test / validate 命令可以验证？

## 11. 禁止事项

明确禁止：

- 在项目根目录随意新增临时文件。
- 在代码里硬编码主机或笔记本路径。
- 删除旧配置或旧脚本。
- 未经确认移动 `scripts/*.py`。
- 未经确认移动 `src/yolo6d_car/config.py`、`path_utils.py`、`pipeline.py`。
- 把真实采集图片、视频、模型权重提交到 Git。
- 把 prototype 功能直接接入正式 pipeline。
- 没有 validate 就声称功能完成。
- 没有说明风险就合并到 main。

## 12. Codex 每次完成任务后必须输出

每次任务完成后，必须输出：

- 新增文件。
- 修改文件。
- 删除 / 移动文件，如果没有就写“无”。
- 是否修改核心流程。
- 是否影响旧命令。
- 是否新增配置。
- 是否新增文档。
- 验证命令和结果。
- 当前 warning。
- 仍需真实硬件验证的内容。
- `git status --short`。
- 是否建议提交 Git。

## 13. 当前阶段建议

当前阶段优先：

- 稳定 Hikrobot 6mm 真实采集链路。
- 完成 Hikrobot 8mm 内参标定。
- 完成 D455 / Hik 连续采集质量验证。
- 完成 RGB 背景墙色彩校正离线实验。
- 暂时不要大规模移动 `scripts`、`configs`、`src`。
