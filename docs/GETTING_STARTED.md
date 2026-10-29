# 环境准备与快速上手

> 目标：让你在自己的电脑上完成基础环境搭建，阅读代码，查看已有结果。
> 无需连接任何实验室设备即可完成本文档的大部分内容。

---

## 1. 开发环境

### Python 版本

项目使用 Python 3（具体最低版本待验证，建议 3.10+）。

### 创建虚拟环境

```bash
# 在项目根目录下创建虚拟环境
python -m venv .venv

# Windows 激活
.venv\Scripts\activate

# Linux / macOS 激活
source .venv/bin/activate
```

### 安装依赖

```bash
pip install -r requirements.txt
```

当前 `requirements.txt` 包含：
```
numpy>=1.24
opencv-python>=4.8
PyYAML>=6.0
scipy>=1.10
ultralytics>=8.3
```

可选依赖（仅实验室设备需要，本地不安装也能阅读代码）：
- `pyrealsense2`：Intel RealSense D455 相机驱动
- `vrpn`：部分 Mocap 实时接入

**CUDA / PyTorch 版本：** 待验证。YOLO 推理可使用 CPU，训练需要 GPU。

### 项目路径配置

当前代码中存在以下本地绝对路径，在其他电脑上需要注意：

| 路径 | 用途 |
|---|---|
| `D:\YOLO6D_Car` | 项目根目录 |
| `D:\CaptureData` | 采集数据、标签输出、标定结果 |
| `E:\MVS` | Hikrobot MVS SDK 安装目录 |

**处理方法：**

1. 克隆项目并进入项目目录：
   ```powershell
   git clone https://github.com/Cryonix0408/YOLO6D_Car.git
   cd YOLO6D_Car
   ```
2. 复制路径示例文件，创建自己的本地配置：
   ```powershell
   Copy-Item .\configs\paths.example.yaml .\configs\paths_local.yaml
   ```
3. 在 `configs/paths_local.yaml` 中将项目路径、数据路径及各子目录改成本机路径；不要把示例路径直接用于采集、训练或标定。

只阅读代码无需设备；配置结构检查和已有小型示例也可以离线使用。采集及真实数据标注需要对应设备或数据。原始数据、训练权重和 `outputs/` 不随仓库分享，需另行获取。不要直接修改 production config 文件中的绝对路径。

---

## 2. 无设备使用模式

以下操作**不需要**任何实验室设备，可在普通电脑上完成。

### 查看已有数据格式

```bash
# 查看 Mocap CSV 格式示例
python -I -c "
import csv
rows = list(csv.reader(open('data/examples/mocap_sample.csv', encoding='utf-8-sig')))
for r in rows[:5]: print(r)
"
```

### 读取 Car Model 结构

```bash
python -I -c "
import json
m = json.load(open('models/car_custom_keypoints_12_current_rigid0_200xx.json'))
print('关键点数量:', len(m['points']))
print('bbox corners:', len(m['bbox_corners_3d']))
for p in m['points']:
    print(' ', p['name'], p['xyz_m'])
"
```

### 验证配置加载

```bash
cd D:\YOLO6D_Car
python scripts/generate_mocap_labels.py \
    --config configs/fzmotion_hikvision_6mm_current_rigid1_20261007_003_labels.yaml \
    --validate-config
```

此命令仅做配置校验，不读取任何采集数据。

### 查看已有标签和 overlay

已有正式 smoke 输出位于：
```
D:\CaptureData\outputs\auto_labels\
    car_static_0004_H1_CY0_D3_L0_B0_formal_smoke_20261015_001\
        labels_yolo_pose\    ← YOLO Pose 格式标签（.txt）
        overlays\            ← 叠加可视化图像（.png）
        summary.json         ← 统计摘要
        annotations.jsonl    ← 元数据
```

### 语法检查所有 Python 文件

```bash
cd D:\YOLO6D_Car
python -m compileall src/ scripts/ -q
```

---

## 3. 实验室设备依赖

以下操作**必须在实验室**完成：

| 设备 | 相关操作 |
|---|---|
| **Hikrobot 工业相机** | 采集原始图像（`scripts/collect_hikvision_sequence.py`）、相机内参标定（`scripts/calibrate_hik_camera.py`） |
| **FzMotion Mocap 系统** | 采集刚体位姿 CSV（`scripts/capture_object_samples.py`）、实时 GT 评估 |
| **ArUco 标定板** | 相机外参标定（Camera rigid to optical 求解） |
| **完整 CaptureData** | 运行自动标注脚本（`scripts/generate_mocap_labels.py --samples-dir ...`） |

---

## 4. 本地绝对路径说明

| 操作 | 是否依赖本地路径 | 说明 |
|---|---|---|
| 阅读 `src/` 下所有源代码 | 否 | 直接阅读，无需任何路径 |
| 阅读 `configs/*.yaml` | 否 | 直接阅读 |
| 运行 `--validate-config` | 否 | 仅校验配置结构 |
| 运行 `generate_mocap_labels.py` | **是** | 需要 `D:\CaptureData` 下的采集数据和 Mocap CSV |
| 运行实时推理 | **是** | 需要相机设备和 `E:\MVS` SDK |
| 运行训练 | **是** | 需要完整数据集和 GPU |

如需在其他路径运行，使用 `--paths-config configs/paths_local.yaml` 参数覆盖路径，不要修改正式 production 配置。

---

## 5. 运行已有可复现示例

### 示例：评估格式检查

```bash
cd D:\YOLO6D_Car
python scripts/evaluate_pose_results.py \
    --gt-csv data/examples/gt_evaluation_test/gt_pose.csv \
    --pred-csv data/examples/gt_evaluation_test/pose_results.csv
```

（确认 `evaluate_pose_results.py` 支持此参数格式后再运行，请先阅读脚本帮助）

### 示例：查看采集质量测试数据

```
data/examples/capture_quality_test/    ← 6 张示例图像 + capture_index.csv
data/examples/sync_test/               ← 时间同步测试样本
```

---

*最后更新：2026-10-29*
