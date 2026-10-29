# 正式版本与 Artifact 指南

> 本文档说明当前项目各类标定结果、模型文件和配置的正式状态。
> 修改任何 `PRODUCTION_VALIDATED` 文件前，必须先咨询项目负责人。

---

## 重要说明

**`validated` 不等于所有物理几何都有独立测量证明。**

- `validated_engineering` 表示已通过工程验证（多 yaw 投影一致性、重投影误差等），但部分几何参数（如 Car Model origin、bbox 底面位置）依赖 legacy migration，尚无独立物理量测。
- 文件状态基于文件内容、正式配置引用关系和验证证据综合判断，不仅凭文件名。

---

## Camera

### 1007 Camera External（外参）

**状态：** `PRODUCTION_VALIDATED`

Camera external（`T_1007Rigid1_CameraOptical`）通过 2026-10-07 solve run 003 确定，保存在正式标签配置中：

```
configs/fzmotion_hikvision_6mm_current_rigid1_20261007_003_labels.yaml
  mocap.T_camera_rigid_to_optical:
    translation_m: [-0.0122, -0.0100, -0.0692]
    quaternion_xyzw: [0.9989, 0.0067, 0.0445, -0.0132]
```

**规则：** 只要 Camera 与 marker assembly 的物理安装关系不变，不重新标定。

---

### Current Rigid1 → 1007 Canonical Rigid1 Bridge

**状态：** `PRODUCTION_VALIDATED`

**文件：**
```
configs/calibration/T_current_rigid1_to_1007_rigid1_validated_20261014.json
```

**含义：** Rigid1 在 2026-10-07 标定后被重建，frame 定义发生了 4.347° 偏转。Bridge 将当前 Rigid1 frame 对齐到 1007 canonical Rigid1 frame，使旧外参继续有效。

**变换方向：**
```
p_CurrentRigid1 = T_CurrentRigid1_1007Rigid1 @ p_1007Rigid1
```

**验证：** 加入 Bridge 后，static0004 六个 yaw（15/30/45/60/75/180°）全部 GOOD；不加 Bridge 全部 LEFT_DOWN。

**重要规则：** Rigid1 rebuild 后应重新 registration 回 canonical，不应直接重标 Camera external。

---

### 1007 Canonical Rigid1 Geometry

**状态：** `PRODUCTION_VALIDATED`

**文件：**
```
configs/calibration/rigid1_geometry_1007_canonical_validated.json
```

包含 4 个 marker（20100–20103）在 Rigid1 frame 中的局部坐标，用于未来 Rigid1 rebuild 时做 registration。marker ID 为 session-local，不是永久物理 ID。

---

### 历史外参文件（请勿直接使用）

下列路径仅作历史溯源，不随本科生最小共享版本提供；如需查阅，请联系项目负责人。

```
configs/calibration/extrinsic_initialization_hik_6mm_20260716.yaml        HISTORICAL
configs/calibration/extrinsic_initialization_hik_6mm_20260802_001.yaml    HISTORICAL
configs/calibration/extrinsic_regression_hik_6mm_20260710.yaml            HISTORICAL
configs/calibration/fast_extrinsic_hik_6mm.yaml                           DIAGNOSTIC_CANDIDATE
configs/calibration/extrinsic_sync_workflow_hik_6mm.yaml                  DIAGNOSTIC_CANDIDATE
```

---

## Car / Rigid0

### 当前正式 Car Model

**状态：** `PRODUCTION_VALIDATED`

**文件：**
```
models/car_custom_keypoints_12_current_rigid0_200xx.json
```

包含：
- 12 个 3D keypoints（车顶 marker 4 个、底盘 4 个、车轮外侧 4 个）
- 8 个 3D bbox corners
- center_3d

**Car Model frame 约定：**
```
+X = 车辆左方
+Y = 向上
+Z = 向前
```

**已知局限：**
- `bbox_corners_3d` 底面 `y = −152.2 mm`，来自 legacy migration，未独立标定 origin
- 视觉验证发现 BBox 底边落在地面以下（约 65–122 px），可能需要调整底面几何
- `keypoints_3d_source = "legacy_migrated_model_pending_frame_calibration"`

**物理 BBox 尺寸（production 正式）：**
```
width  = 255.368 mm
height = 147.000 mm
length = 260.635 mm
```

> **注意：** 2026-10-18 实测候选尺寸（227×155×261 mm）仍是候选值，未完成多 yaw 验证，**不得覆盖当前正式模型**。

---

### 当前正式 Rigid0 Registration

**状态：** `PRODUCTION_VALIDATED`

**文件：**
```
configs/calibration/T_current_rigid0_from_canonical_car_model_validated_20261015.json
```

**变换方向：**
```
p_CurrentRigid0 = T_CurrentRigid0_CanonicalCarModel @ p_CanonicalCarModel
```

**验证：** static0004 六个 yaw multi-yaw 一致性 PASS，production regression PASS，physical BBox production regression PASS。

**已知局限：**
- registration 接近 identity（rotation 偏差 1.06°，translation 约 1e-5 m）
- 这反映了迁移前后坐标系对齐良好，但不等于已独立物理验证 Car Model origin

---

### Rigid0 历史文件

下方诊断 registration 随共享版本提供；correspondences 文件仅作历史溯源，不随本版本提供。

```
configs/calibration/rigid0_to_canonical_car_model_registration_20261013_diagnostic.json   HISTORICAL（production 的诊断来源）
configs/calibration/rigid0_to_car_model_correspondences_20261013.json                     HISTORICAL
```

---

## 重要 Epoch 限制

### Rigid0 Epoch 区分

| Epoch | 状态 | 说明 |
|---|---|---|
| 2026-10-15 及之前 | PRODUCTION_VALIDATED | 当前正式 registration 所针对的 Rigid0 定义 |
| 2026-10-18 新数据 | DIAGNOSTIC_CANDIDATE | 新版 Rigid0 静态数据，geometry registration 最优 RMS ≈ 12.277 mm（远高于旧版 3.514 mm） |

**规则：**
- **新版 Rigid0（2026-10-18）不能直接套用旧 `T_CurrentRigid0_CanonicalCarModel`。**
- 新旧 Rigid0 的 marker 定义不同，必须重新做 marker-ID-independent registration。
- 若新版 Rigid0 数据中 Rigid1 存在帧间跳变（P90 ≈ 2.221°），需先排查原因再用于 production。

---

## Label Config

### 当前正式标签配置

**状态：** `PRODUCTION_VALIDATED`

**文件：**
```
configs/fzmotion_hikvision_6mm_current_rigid1_20261007_003_labels.yaml
```

引用了所有 production artifact（Camera external、Bridge、Rigid0 Registration、Car Model），并记录了 SHA256。

**已通过验证：**
- static0004 formal smoke：6 帧格式验证（41 字段）PASS
- BBox 数值复现：6 帧最大差 0.00 px，PASS

**尚未完成：**
- 12 个关键点逐点视觉语义验收
- BBox 物理边界准确性待验证（底面 3D 位置与实际车轮轮廓的对应关系尚未独立测量确认）

---

## 其他重要文件状态

本节列出的候选文件仅作历史溯源，不随本科生最小共享版本提供；如需查阅，请联系项目负责人。

| 文件 | 状态 | 说明 |
|---|---|---|
| `configs/calibration/car_model_physical_geometry_20261014_diagnostic.json` | `DIAGNOSTIC_CANDIDATE` | 2026-10-14 物理测量候选，未 promotion |
| `configs/calibration/board_rigid_to_aruco_validated_engineering_20261014_diagnostic_adapter.json` | `DIAGNOSTIC_CANDIDATE` | ArUco board 标定适配器 |
| `configs/fzmotion_hikvision_6mm_session002_bridge_candidate.yaml` | `DIAGNOSTIC_CANDIDATE` | Bridge 候选配置，未 promotion |
| `configs/fzmotion_hikvision_6mm_current_rigid0_marker_check.yaml` | `UNKNOWN` | marker check 用途，未确认是否仍适用 |
| `configs/calibration/hik_6mm_calibration.yaml`、`hik_8mm_calibration.yaml` | `UNKNOWN` | 内参标定文件，未核查当前适用性 |

---

## 坐标系约定（核心）

```
p_A = T_A_B @ p_B    （T_A_B 表示 B → A 的变换）

T_A_B @ T_B_C = T_A_C

正式 Camera Chain：
T_W_CameraOptical =
    T_W_CurrentRigid1
    @ T_CurrentRigid1_1007Rigid1   ← Bridge
    @ T_1007Rigid1_CameraOptical   ← Camera External

正式 Car Chain：
T_W_CarModel =
    T_W_CurrentRigid0
    @ T_CurrentRigid0_CanonicalCarModel
```

**禁止：** 凭变量名猜测变换方向，未验证就对 transform 取逆，把 Rigid1 frame 当作 Camera Optical frame。

---

*最后更新：2026-10-29*
