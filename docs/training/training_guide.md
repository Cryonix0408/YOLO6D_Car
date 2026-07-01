# 训练说明

## 1. 当前推荐数据集

当前推荐训练数据集为：

- [uav_4m_20sessions_pose_20260413_v1_clean](../outputs/datasets/uav_4m_20sessions_pose_20260413_v1_clean)
- 数据集入口：
  [dataset.yaml](../outputs/datasets/uav_4m_20sessions_pose_20260413_v1_clean/dataset.yaml)

该数据集特点：

- 共 20 个 session
- 单类目标 `car_model`
- 12 个关键点
- 已过滤空图问题

## 2. 当前推荐训练方式

推荐从上一版最佳权重继续 fine-tune：

```powershell
python .\scripts\train_ultralytics_pose.py `
  --dataset .\outputs\datasets\uav_4m_20sessions_pose_20260413_v1_clean\dataset.yaml `
  --model .\outputs\train_runs\uav_4m_20sessions_pose_v1\weights\best.pt `
  --epochs 120 `
  --imgsz 640 `
  --batch 16 `
  --workers 4 `
  --patience 40 `
  --project .\outputs\train_runs `
  --name uav_4m_20sessions_pose_v1
```

如果要从头训练，把 `--model` 换成：

```text
yolov8n-pose.pt
```

## 3. 重新整理数据集

重新生成同名数据集时，脚本默认会拒绝写入已有的 `images/`、`labels/`、`dataset.yaml` 或 `split_summary.json`，避免旧样本混进新数据集。

确认输出目录可以重建后，显式加：

```powershell
--overwrite
```

例如：

```powershell
python .\scripts\prepare_yolo_pose_dataset.py `
  --auto-label-dir .\outputs\auto_labels\<session_name> `
  --out-dir .\outputs\datasets\<dataset_name> `
  --overwrite
```

## 4. 输出位置

训练输出默认在：

- [uav_4m_20sessions_pose_v1](../outputs/train_runs/uav_4m_20sessions_pose_v1)

重点关注这些文件：

- `weights/best.pt`
- `weights/last.pt`
- `results.csv`
- `results.png`
- `val_batch*_pred.jpg`

## 5. 训练后怎么选模型

默认使用：

- `best.pt`

不要默认使用：

- `last.pt`

原因：

- `best.pt` 是按验证集指标选出的最优权重
- `last.pt` 只是最后一个 epoch 的状态，不一定是泛化最好的版本

## 6. 训练完成后的下一步

1. 抽查 `val_batch*_pred.jpg`
2. 记录训练配置与结果目录
3. 把实时配置里的 `model_path` 更新到新的 `best.pt`
4. 再做实时联调

## 7. 常用命令

### 查看数据集 YAML

```powershell
Get-Content .\outputs\datasets\uav_4m_20sessions_pose_20260413_v1_clean\dataset.yaml
```

### 查看训练结果目录

```powershell
Get-ChildItem .\outputs\train_runs\uav_4m_20sessions_pose_v1
```


