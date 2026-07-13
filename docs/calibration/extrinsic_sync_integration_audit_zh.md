# 外参时间同步工作流接口审计

本文档记录 `solve_camera_rigid_to_optical.py`、`verify_camera_rigid_to_optical.py` 与 `extrinsic_sync_workflow.py` 的只读接口审计结果，为后续安全接入“外参 + 时间同步标准工作流”提供依据。

- 审计日期：2026-07-13
- 项目根目录：`D:\YOLO6D_Car`
- 当前分支：`codex/color-correction-prototype`
- 审计方式：静态阅读源码、配置、文档与 Git diff；未连接相机、未采集数据、未运行正式求解或验证。
- 本轮边界：只新增本文档，不修改任何代码或配置。

## 1. solve 脚本当前结构

目标文件：`scripts/solve_camera_rigid_to_optical.py`

### 1.1 CLI 参数

| 参数 | 必需 | 默认值 | 作用 |
| --- | ---: | --- | --- |
| `--config` | 是 | 无 | 项目配置，提供 Mocap 刚体名、时间容差、默认 offset 和外参初值等。 |
| `--samples-dir` | 是 | 无 | 采集 session；内部寻找 `samples.csv` 或 `camera_timestamps.csv` 及图像。 |
| `--board-rigid-body` | 是 | 无 | FzMotion 中标定板刚体名称。 |
| `--markers-x` / `--markers-y` | 是 | 无 | ArUco GridBoard 横纵 marker 数。 |
| `--marker-length-mm` | 是 | 无 | 单个 marker 边长，毫米。 |
| `--marker-separation-mm` | 是 | 无 | marker 间隔，毫米。 |
| `--dictionary` | 是 | 无 | OpenCV ArUco 字典名。 |
| `--csv-path` | 否 | 配置中的 `mocap.csv_path` | 覆盖 FzMotion CSV。 |
| `--intrinsics-path` | 否 | 自动搜索 | 指定内参 JSON/YAML。 |
| `--timestamp-start-local-time` | 否 | `None` | 为缺失本地时间的旧数据指定采集起点。 |
| `--time-offset-s` | 否 | 配置中的 `mocap.time_offset_s` | 相机时间转到 Mocap 时间轴时添加的偏移。 |
| `--stationary-only` | 否 | 关闭 | 只使用近似静止的标定板帧。 |
| `--stationary-window-s` | 否 | `0.20` | 运动估计的半时间窗。 |
| `--max-board-speed-mps` | 否 | `0.02` | 静止筛选最大平移速度。 |
| `--max-board-angular-speed-deg-s` | 否 | `5.0` | 静止筛选最大角速度。 |
| `--robust-reject-px` | 否 | `0.0` | 大于 0 时按板外轮廓投影误差剔除异常样本。 |
| `--robust-reject-iterations` | 否 | `1` | 异常剔除和重新求解的最大轮数。 |
| `--robust-min-samples` | 否 | `30` | 鲁棒剔除后允许保留的最少样本数。 |
| `--camera-init-config` | 否 | `None` | 从另一配置加载相机外参初值和软先验。 |
| `--no-camera-prior` | 否 | 关闭 | 禁用相机外参初值/先验。 |
| `--camera-translation-prior-sigma-m` | 否 | `0.08` | 平移软先验标准差。 |
| `--camera-rotation-prior-sigma-deg` | 否 | `12.0` | 旋转软先验标准差。 |
| `--out` | 否 | `outputs/calibration/camera_rigid_to_optical.json` | 求解结果 JSON。 |

### 1.2 `main()` 与关键函数

`main()` 当前同时承担参数解析、路径解析、CSV 加载、时间转换、帧筛选、ArUco 检测、观测构造、联合优化、鲁棒剔除、JSON 写入和终端打印。主要内部能力如下：

| 函数/类型 | 当前作用 |
| --- | --- |
| `Observation` | 保存同一时刻的图像、相机刚体、标定板刚体和视觉板位姿。 |
| `BoardDetection` | 保存视觉检测得到的 `T_camera_board_visual` 和 marker 数。 |
| `load_intrinsics()` | 兼容 Hik YAML、标定 summary JSON 和旧 D455 JSON。 |
| `find_intrinsics_path()` | 自动寻找内参；包含 `D:/CaptureData/...` 硬编码候选。 |
| `detect_board_pose()` | 检测 GridBoard 并估计视觉板位姿。 |
| `load_sample_rows()` | 读取并归一化 `samples.csv` 或 `camera_timestamps.csv`。 |
| `_resolve_sample_timestamp_s()` | 将本地/Unix/设备时间转换为 Mocap 相对秒。 |
| `estimate_rigid_motion()` | 用时间窗两端的最近邻 Mocap 位姿估计速度。 |
| `optimization_residuals()` | 构造相机外参、板刚体外参及相机软先验的优化残差。 |
| `solve_calibration()` | 调用 `scipy.optimize.least_squares`。 |
| `observation_projection_errors()` | 计算每帧板外轮廓平均投影误差。 |
| `summarize_values()` | 输出 mean、median、p90、max。 |

### 1.3 输入与输出

输入包括项目配置、采集 session、图像、相机时间戳、FzMotion CSV、相机内参、板规格，以及可选相机外参初值。输出 JSON 包含：

- `T_camera_rigid_to_optical`：`translation_m`、`quaternion_xyzw`、`matrix`。
- `T_board_rigid_to_board_visual`：同样的三种表达。
- `num_used_samples`、`optimization_success`、`optimization_message`。
- `metadata`：输入路径、刚体名、板规格、时间偏移、静止筛选统计、跳过统计、鲁棒剔除历史和最终投影误差。

### 1.4 时间偏移、静止筛选与可导入性

- `time_offset_s` 在 `_resolve_sample_timestamp_s()` 得到基础时间后执行 `timestamp += time_offset_s`，随后用于静止筛选和两个刚体位姿查询。符号语义是“加到相机帧时间上，再查询 Mocap”。
- `stationary-only` 已实现，但运动估计依赖 `CSVRigidBodyProvider.get_pose()` 的最近邻查询，不是连续位姿插值。
- 模块有 `if __name__ == '__main__': main()`，导入时不会执行 CLI，也不会初始化真实相机。
- 导入时会检查 `opencv-contrib-python` 和 `cv2.aruco`；缺失依赖会立即抛错。
- 多个函数可以直接 import，但完整流程仍绑定 `argparse.Namespace`、文件写入和 `main()`，缺少稳定的 `request -> result` 公共 API。

## 2. verify 脚本当前结构

目标文件：`scripts/verify_camera_rigid_to_optical.py`

### 2.1 CLI 参数与内部结构

必需参数为 `--config`、`--samples-dir`、`--csv-path`、`--intrinsics-path`、`--calibration-json`、`--board-rigid-body`、板规格、字典和 `--output-dir`；可选参数为 `--save-count`、`--time-offset-s` 及静止筛选参数。

主要函数为：

- `load_transform()`：从求解 JSON 读取 4x4 矩阵。
- `create_board()`、`board_outline_points()`：构造 GridBoard 和物理外轮廓。
- `project_points()`：3D 板点投影。
- `pose_error()`：计算平移误差和旋转误差。
- `draw_polygon()`：绘制视觉与 Mocap 投影轮廓。
- `main()`：完成全部读取、筛选、检测、指标统计与文件输出。

值得注意的是，verify 通过把 `scripts/` 加入 `sys.path`，直接从 solve 脚本导入 `_parse_fzmotion_start_time`、`_resolve_sample_timestamp_s`、`detect_board_pose`、`estimate_rigid_motion`、`load_intrinsics` 和 `load_sample_rows`。这是脚本间私有接口耦合，不是稳定的包级 API。

### 2.2 输入、输出和指标

verify 读取求解 JSON 中的 `T_camera_rigid_to_optical` 和 `T_board_rigid_to_board_visual`，对每个有效帧比较视觉 ArUco 位姿与 Mocap 变换链。输出包括：

- `verification_samples.csv`：逐帧时间戳、marker 数、角点投影误差、平移误差、旋转误差和可选板速度。
- `verification_summary.json`：有效样本数、时间偏移、筛选/跳过统计和汇总指标。
- `overlays/verify_*.png`：视觉轮廓（绿色）与 Mocap 投影（青色）。

三类指标均包含 `mean`、`median`、`p90`、`max`：

- `mean_corner_error_px`
- `translation_error_m`
- `rotation_error_deg`

### 2.3 holdout、overlay 与可导入性

- **不支持显式 holdout frame 列表。** 当前会验证筛选后的全部有效帧，也没有 `include/exclude sample_index` 参数。因此“求解集与验证集隔离”尚未实现。
- 支持 overlay；`--save-count` 在全部有效样本中等间隔选帧保存。
- 模块受 `if __name__ == '__main__'` 保护，导入不会运行 CLI 或初始化硬件。
- 辅助函数可导入，但完整验证仍绑定 `argparse.Namespace`、输出目录和 `main()`；尚无结构化验证入口。

## 3. 当前数据契约

### 3.1 相机样本与时间戳

| 来源 | 必需字段 | 可选字段 | 当前行为 |
| --- | --- | --- | --- |
| `samples.csv` | `sample_index`、`image_path`、`device_timestamp_s` | `saved_local_time`、`saved_unix_time_s` | 原样读入。 |
| `camera_timestamps.csv` | `image_path`、`timestamp` | `saved_local_time`、`saved_unix_time_s` | `sample_index` 由行号生成，`timestamp` 映射为 `device_timestamp_s`。 |

当前 solve/verify **不消费 `frame_id` 字段**。时间源优先级为：

1. `saved_local_time` 相对 FzMotion `StartTime`；
2. `saved_unix_time_s` 相对 FzMotion `StartTime`；
3. `device_timestamp_s` / `timestamp`。

旧 Hik 数据如果缺少本地时间，会尝试用第一张图 Windows 创建时间和配置 FPS 推算；该方式精度和可复现性弱，应在正式工作流中显式标记为 legacy fallback。

### 3.2 Mocap CSV

`CSVRigidBodyProvider` 支持：

- 通用 CSV：`timestamp, rigid_body, tx, ty, tz, qx, qy, qz, qw`。
- FzMotion 多行表头 CSV：从 `DataName`、`StartTime`、`LengthUnits` 及 Rigid Body 的 Rotation/Position 列解析。

FzMotion 位移按 `LengthUnits` 转为米；四元数顺序为 `xyzw`。查询接口 `get_pose(rigid_body, timestamp_s, max_time_diff_s)` 只返回容差内最近邻位姿，**没有平移线性插值或四元数 SLERP**。

### 3.3 刚体、内参与变换

- 相机刚体名：`config.mocap.camera_rigid_body`。
- 标定板刚体名：CLI `--board-rigid-body`。
- 时间查询容差：`config.mocap.max_time_diff_s`。
- 内参格式：Hik YAML（`camera`、字典型 `camera_matrix`、`distortion.vector`）、标定 summary JSON（矩阵列表）或旧 D455 flat JSON。
- 求解输出 `T_camera_rigid_to_optical`：4x4 矩阵及平移/四元数。
- 求解输出 `T_board_rigid_to_board_visual`：4x4 矩阵及平移/四元数。

### 3.4 workflow 与现有脚本的契约差异

workflow 配置声明了 `camera_timestamps_csv`、`image_dir` 和 `board_rigid_to_aruco_path`，但现有 solve/verify 的契约是传入一个包含时间戳 CSV 与图像路径的 `samples-dir`。更关键的是：

- 当前 solve **不读取** `board_rigid_to_aruco_path`；它会与相机外参一起联合估计 `T_board_rigid_to_board_visual`。
- 当前 verify 也不接受独立的 `board_rigid_to_aruco`，而是要求 calibration JSON 同时包含相机和板的两个变换。
- `board_visual` 与 workflow 中 `aruco` 的坐标系命名是否严格等价，目前没有独立机器可读契约，必须在集成前统一定义，不能仅靠变量名推断。

## 4. 可复用能力表

| 能力 | 当前所在文件/函数 | 可直接复用 | 需要轻量抽取 | 需要重写 | 风险 |
| --- | --- | :---: | :---: | :---: | --- |
| 读取相机时间戳 | solve / `load_sample_rows()` |  | 是 |  | 位于脚本；legacy 时间推算依赖文件创建时间。 |
| 读取 Mocap CSV | `mocap/csv_provider.py` / `CSVRigidBodyProvider` | 是 |  |  | 当前一次性读完整 CSV，且只提供最近邻查询。 |
| 时间插值 | 当前不存在 |  |  | 是（新增能力） | 最近邻会把采样相位误差混入 offset 与外参。 |
| 应用 time offset | solve/verify 的 `main()` |  | 是 |  | 两处重复；必须固定偏移符号定义。 |
| ArUco 检测 | solve / `detect_board_pose()` |  | 是 |  | 位于脚本并依赖 OpenCV 版本兼容分支。 |
| stationary frame selection | solve / `estimate_rigid_motion()` 与两处主循环 |  | 是 |  | 速度基于窗口端点最近邻；筛选策略尚无独立结果对象。 |
| 外参求解 | solve / `optimization_residuals()`、`solve_calibration()` |  | 是 |  | `Observation` 和初始化/鲁棒循环仍在脚本中。 |
| reprojection error | solve / `observation_projection_errors()`；verify / `project_points()` |  | 是 |  | solve/verify 有重复几何代码，轮廓误差不是检测角点逐点误差。 |
| holdout verification | 当前不存在显式 holdout 接口 |  |  | 是（新增能力） | 当前验证集与求解集可能重叠，不能作为严格泛化证据。 |
| overlay | verify / `draw_polygon()` 与 `main()` |  | 是 |  | 当前抽样策略只按有效序列等间隔，不理解 holdout。 |
| JSON/CSV 输出 | solve/verify 的 `main()` |  | 是 |  | 结构化文件可沿用，但写入和计算未解耦。 |

`src/yolo6d_car/pose/` 当前主要负责 PnP、YOLO 后端和时间滤波，不参与外参求解；不建议为了本工作流把标定逻辑放入 `pose/`。

## 5. 推荐集成方式

| 方案 | 优点 | 缺点 | 结论 |
| --- | --- | --- | --- |
| A. workflow 用 subprocess 调旧 CLI | 改动最少，旧脚本立即可执行；JSON 输出可作为临时接口。 | 每个 offset 都重新加载 CSV/图像；参数和错误传播笨重；难做内存级 train/holdout；容易诱发解析 stdout。 | 可作为短期人工过渡，不建议成为正式科研接口。 |
| B. 从旧脚本抽公共函数到 `src` | 单次加载后可重复扫描 offset；可用类型化 request/result；容易单测；旧 CLI 可保留 wrapper。 | 需要谨慎拆分并做回归测试。 | **推荐。** |
| C. workflow 复制旧逻辑 | 初期看似独立。 | 产生两套时间、检测、几何和指标实现，后续必然漂移。 | 不采用。 |

推荐方案 B：把公共逻辑放入 `src/yolo6d_car/calibration/`，让两个旧根目录脚本继续作为兼容 wrapper。workflow 应调用 Python 结构化 API，并使用返回对象或 JSON/CSV 文件作为正式数据接口；**不得解析终端文本**。subprocess 只可作为公共函数尚未落地前的临时桥接，而且也只能读取结构化输出文件。

## 6. 最小安全实施计划

### 6.1 建议新增的公共接口

建议先增加两个小模块，而不是一次重写整个流程：

- `src/yolo6d_car/calibration/extrinsic_calibration.py`：板规格、帧记录、时间转换、观测构造、静止筛选、ArUco 检测、联合求解和投影统计。
- `src/yolo6d_car/calibration/extrinsic_verification.py`：显式 holdout 选择、逐帧验证、汇总统计和 overlay 写入。

建议的核心签名示意：

```python
def load_extrinsic_frames(samples_dir: Path, *, timestamp_start_local_time: str | None = None) -> list[FrameRecord]: ...

def build_extrinsic_observations(
    frames: Sequence[FrameRecord],
    provider: CSVRigidBodyProvider,
    request: ObservationBuildRequest,
) -> ObservationBuildResult: ...

def solve_camera_rigid_extrinsic(request: ExtrinsicSolveRequest) -> ExtrinsicSolveResult: ...

def verify_camera_rigid_extrinsic(request: ExtrinsicVerifyRequest) -> ExtrinsicVerifyResult: ...
```

`ExtrinsicVerifyRequest` 必须显式接收 `frame_indices` 或 `holdout_indices`，而不是默认复用全部帧。`ExtrinsicSolveResult` 和 `ExtrinsicVerifyResult` 应提供 `to_dict()`，CLI 只负责参数转 request、调用和保存。

时间查询建议在 `src/yolo6d_car/mocap/` 增加明确接口，例如：

```python
def get_interpolated_pose(
    self,
    rigid_body: str,
    timestamp_s: float,
    max_time_diff_s: float,
) -> PoseSE3 | None: ...
```

平移使用线性插值，旋转使用 quaternion SLERP；旧 `get_pose()` 保留以保证兼容。是否启用插值必须写入运行证据。

### 6.2 旧脚本改造边界

- `scripts/solve_camera_rigid_to_optical.py`：保留全部 CLI 参数、默认值、stdout 关键行和 JSON 字段；只把计算委托给公共 API。
- `scripts/verify_camera_rigid_to_optical.py`：保留旧参数和现有输出；新增 holdout 参数时必须是向后兼容的可选参数。
- `src/yolo6d_car/calibration/extrinsic_sync_workflow.py`：调用结构化公共 API，负责 offset 网格、train/holdout 划分、最佳 offset 选择、证据链和质量分级。
- `src/yolo6d_car/mocap/csv_provider.py`：仅新增插值接口，不改变旧最近邻接口行为。

### 6.3 synthetic tests

建议使用不含真实图像和硬件的小型合成测试：

1. 构造已知匀速平移和匀角速度的两帧 Mocap 位姿，验证中间时刻线性插值与 SLERP。
2. 合成已知 `T_camera_rigid_to_optical`、`T_board_rigid_to_visual` 和多组世界位姿，生成无噪声 `Observation`，验证求解可恢复真值。
3. 注入已知 `time_offset_s`，扫描 offset 后验证最优值落在一个步长内。
4. 用固定随机种子划分 train/holdout，断言无交集、全集守恒且结果可复现。
5. 给少量观测加入大误差，验证鲁棒剔除记录、最小样本保护和统计结果。
6. 对旧 CLI 做 3 帧小样例回归，比较 JSON schema 与关键 stdout 行，确保旧命令不变。

### 6.4 建议 commit 拆分

1. `refactor(calibration): extract extrinsic solve and verification APIs`
   新增公共类型/函数和 synthetic tests，但暂不接 workflow；旧 CLI 改为 wrapper 并做 schema 回归。
2. `feat(mocap): add explicit interpolated pose lookup`
   新增插值接口与数学单测，保留最近邻接口；在证据中记录查询模式。
3. `feat(calibration): integrate extrinsic sync solve and holdout verification`
   workflow 接入 offset 扫描、固定划分、结构化求解/验证和完整证据链。

若希望只分两个 commit，可将第 2 项合入第 1 项，但不建议把公共抽取、插值和 workflow 串联全部塞进同一个 commit。

## 7. marker size 检查

| 文件 | 字段/位置 | 当前值 | 单位 | 用途 |
| --- | --- | ---: | --- | --- |
| `configs/calibration/extrinsic_sync_workflow_hik_6mm.yaml` | `calibration.marker_length_mm` | 28.05 | mm | workflow 的 GridBoard marker 边长。 |
| 同上 | `calibration.marker_size_m` | 0.02805 | m | 同一物理尺寸的米制重复字段；当前 scaffold 未用于 solve。 |
| 同上 | `calibration.marker_separation_mm` | 12.0 | mm | GridBoard marker 间隔。 |
| `scripts/solve_camera_rigid_to_optical.py` | `--marker-length-mm` | 无默认，必填 | mm | 创建 GridBoard、计算板外轮廓并写入 metadata。 |
| `scripts/verify_camera_rigid_to_optical.py` | `--marker-length-mm` | 无默认，必填 | mm | 创建 GridBoard和计算验证外轮廓。 |
| `docs/calibration/extrinsic_sync_workflow_zh.md` | 推荐尺寸 | 28.05 | mm | 当前 Hik 6mm 工作流建议实测值。 |
| `docs/calibration/camera_rigid_calibration.md` | 旧命令示例 | 28 | mm | 历史 D455/旧流程命令示例。 |

结论：`0.02805 m` 与 `28.05 mm` 是一致的；可执行配置中未发现字面量 `0.028 m`，但旧文档命令仍使用 `28 mm`，其物理含义就是 `0.028 m`。因此项目内确实存在 **28.00 mm 与 28.05 mm 两套口径并存**。差值为 0.05 mm（约 0.178%），通常不是几十像素投影误差的主因，但会形成不可追溯的系统尺度差，正式科研工作流必须固定唯一实测值并记录到 resolved config。本文档按要求不修改任何值。

此外，workflow 同时保留 `marker_length_mm` 和 `marker_size_m`，存在双源漂移风险。后续应确定一个权威字段，另一个只做派生值或加载时一致性校验。

## 8. 当前已修改核心脚本审计

以下结论来自工作区现有 diff；本轮没有撤销、暂存或修改这些内容。

| 文件 | 既有未提交改动摘要 | 与 extrinsic sync workflow 的关系 |
| --- | --- | --- |
| `scripts/calibrate_hik_camera.py` | 新增 `--start-paused`、`--manual-stop`，并传给 `run_capture_session()`。 | 上游采集控制和数据质量相关，但不是 solve/verify 集成逻辑。 |
| `scripts/capture_object_samples.py` | 新增预览后按 `s` 开始、手动停止、忽略目标样本上限和 HUD/按键提示调整。 | 属于通用对象采集控制；与 workflow 仅有间接输入质量关系。 |
| `scripts/solve_camera_rigid_to_optical.py` | 新增时间偏移、静止帧筛选、运动速度估计、鲁棒投影误差剔除、统计和结构化 metadata。 | **直接属于本功能基础能力**，也是下一阶段公共 API 抽取的主要来源。 |
| `scripts/verify_camera_rigid_to_optical.py` | 新增时间偏移、静止帧筛选、跳过统计及逐帧速度字段。 | **直接属于本功能基础能力**；但显式 holdout 仍缺失。 |

当前四个脚本 diff 合计约 `+345/-21`。其中 solve/verify 与本功能直接相关；两个采集入口是此前采集交互改进，不应与下一阶段的接口抽取混为一个 commit。

## 审计结论

1. 当前 solve/verify 的数学和文件输出能力已有较好基础，但计算流程仍集中在 CLI `main()`。
2. 正式集成推荐方案 B：抽取包级结构化 API，旧 CLI 保持 wrapper 和输出兼容。
3. 当前最大科研风险是：最近邻位姿查询、求解/验证帧未隔离，以及 workflow 的 `board_rigid_to_aruco` 契约与现有联合估计输出不一致。
4. workflow 不应通过解析 stdout 获取结果；应消费 Python result 或固定 JSON/CSV schema。
5. 在完成插值、显式 holdout 和坐标系契约统一前，不应宣称完整 extrinsic sync workflow 已经落地。
