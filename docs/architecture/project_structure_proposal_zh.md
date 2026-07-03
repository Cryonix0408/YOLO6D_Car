# YOLO6D_Car 推荐项目结构设计

生成日期：2026-07-01  
本方案是设计建议，不表示已经执行迁移。

## 1. 推荐目标结构

```text
YOLO6D_Car/
├── README.md
├── requirements.txt
├── configs/
│   ├── paths/
│   ├── cameras/
│   ├── capture/
│   ├── calibration/
│   ├── labeling/
│   ├── tracking/
│   ├── replay/
│   ├── evaluation/
│   ├── sessions/
│   ├── datasets/
│   └── models/
├── src/yolo6d_car/
│   ├── camera/
│   ├── calibration/
│   ├── mocap/
│   ├── labeling/
│   ├── dataset/
│   ├── pose/
│   ├── tracking/
│   ├── evaluation/
│   ├── management/
│   └── utils/
├── scripts/
│   ├── calibration/
│   ├── capture/
│   ├── labeling/
│   ├── dataset/
│   ├── training/
│   ├── replay/
│   ├── tracking/
│   ├── evaluation/
│   ├── management/
│   ├── sync/
│   └── dev/
├── docs/
│   ├── index.md
│   ├── architecture/
│   ├── setup/
│   ├── cameras/
│   ├── calibration/
│   ├── capture/
│   ├── labeling/
│   ├── training/
│   ├── evaluation/
│   ├── experiments/
│   ├── literature/
│   └── archive/
├── tests/
└── data/examples/
```

## 2. 为什么适合当前项目

当前项目已经从单一 D455 固定相机，扩展到 D455、Hikrobot 6mm、Hikrobot 8mm、Webcam、固定相机、移动相机、mocap 自动标签、YOLO Pose、PnP、Kalman、evaluation 等多条链路。继续把所有配置和脚本平铺在根目录，会增加误用风险。

推荐结构的目标不是过度工程化，而是把“相机、采集、标定、标签、训练、replay、tracking、evaluation、同步管理”按研究流程分层，让实验现场更难复制错命令。

## 3. 现在就可以低风险调整的内容

| 内容 | 原因 | 风险 |
| -- | -- | -- |
| 新增 `docs/index.md` | 给文档入口，不影响代码 | 低 |
| 新增 `docs/archive/` 清单 | 先规划归档，不移动文件 | 低 |
| README 简化为入口页 | 减少 README 过长 | 低 |
| 文档中标注“推荐命令/旧命令” | 避免误用 | 低 |
| `.gitignore` 补充建议 | 可先仅报告，不马上改 | 低 |

## 4. 暂时不建议马上动的内容

| 内容 | 原因 | 风险 |
| -- | -- | -- |
| 移动 `scripts/*.py` | 旧命令和文档会失效 | 高 |
| 移动 `src/yolo6d_car/config.py` | 老 pipeline 依赖多 | 高 |
| 删除旧配置 | D455/Hik 当前还在并行验证 | 高 |
| 合并 D455/Hik 配置 | 容易误伤已验证链路 | 高 |
| 移动 `data/examples/` | smoke tests 可能依赖 | 中 |

## 5. 配置结构建议

| 建议目录 | 放什么 | 当前迁移建议 |
| -- | -- | -- |
| `configs/paths/` | `paths_local.yaml`, `paths_laptop.yaml` | Phase B |
| `configs/cameras/` | D455/Hik/Webcam 硬件参数 | 已基本完成 |
| `configs/capture/` | 自动采集参数 | 已基本完成 |
| `configs/calibration/` | 内参标定配置 | 已基本完成 |
| `configs/labeling/` | mocap 自动标签、外参配置 | 后续迁移 |
| `configs/tracking/` | Kalman 参数 | 后续迁移 |
| `configs/replay/` | smoke/replay 配置 | 后续迁移 |
| `configs/sessions/` | session manifest | 后续迁移 |
| `configs/datasets/` | dataset manifest | 后续迁移 |
| `configs/models/` | model registry | 后续迁移 |

## 6. 源码结构建议

| 建议目录 | 放什么 | 是否现在需要 |
| -- | -- | -- |
| `camera/` | 相机后端和 factory | 已有 |
| `calibration/` | 内参标定、棋盘格检测 | 已有 |
| `mocap/` | CSV provider、刚体插值 | 已有 |
| `labeling/` | mocap label generation 的可复用逻辑 | 建议后续新增 |
| `dataset/` | YOLO dataset 构建逻辑 | 建议后续新增 |
| `management/` | session/dataset/model registry | 中期可迁移 |
| `utils/` | path/config/通用工具 | 中期可迁移 |

## 7. 脚本结构建议

短期不移动脚本，长期可按功能拆分：

| 建议目录 | 放什么 |
| -- | -- |
| `scripts/capture/` | 采集相关入口 |
| `scripts/calibration/` | 内参/外参/验证 |
| `scripts/labeling/` | 自动标签、可视化 |
| `scripts/dataset/` | dataset 构建 |
| `scripts/training/` | 训练 |
| `scripts/replay/` | replay/smoke |
| `scripts/tracking/` | Kalman/ablation |
| `scripts/evaluation/` | GT evaluation |
| `scripts/management/` | session/dataset/model 管理 |
| `scripts/sync/` | 主机/笔记本同步 |
| `scripts/dev/` | 临时测试、prototype |

## 8. 如何保持旧命令兼容

如果未来移动脚本，建议保留根目录 wrapper，例如：

```python
# scripts/generate_mocap_labels.py
from yolo6d_car.cli.labeling.generate_mocap_labels import main

if __name__ == "__main__":
    main()
```

或者先只在文档中引导新命令，旧脚本保留 1-2 个实验周期，等确认主机/笔记本都迁移后再删除。

## 9. 如何避免路径混乱

1. 所有数据路径统一相对 `data_root` 解析。
2. 笔记本使用 `configs/paths_laptop.yaml`。
3. 主机使用 `configs/paths_local.yaml`。
4. 文档命令必须显式写 `--paths-config`。
5. 不再新增 `*_gdrive.yaml`，除非临时兼容。
6. `D:\CaptureData` 和 `G:\YOLO6D_Car_Data` 不写入代码，只写入 paths 配置。

## 10. 如何避免大数据进 Git

1. 所有真实采集数据放 `D:\CaptureData` 或主机 `G:\YOLO6D_Car_Data`。
2. 仓库只保留 `data/examples/` 小样例。
3. 权重、视频、图片、npy/npz、日志都 ignore。
4. 每次 commit 前运行 `git status --short` 检查是否误加入大文件。

## 11. 当前是否建议真实移动文件

**No。**

现在项目正处在 Hikrobot 真实采集和标定调试阶段，先不要移动脚本或配置。推荐先做文档索引、归档清单、命令入口统一，等 Hik 6mm 链路稳定后再做 Phase B/C。

