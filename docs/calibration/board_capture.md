# 标定板采集

使用 [capture_board_samples.py](../scripts/capture_board_samples.py) 从 D455 手动采集标定板样本。

## 1. 推荐做法

1. 同时开始 D455 和 FzMotion 录制
2. 将标定板摆到一个姿态后保持静止
3. 按一次空格保存一帧
4. 更换姿态，继续重复

建议覆盖：

- 近、中、远距离
- 左右偏移
- 上下俯仰
- 适当旋转角度

## 2. 运行命令

```powershell
python .\scripts\capture_board_samples.py --config .\configs\board_capture.yaml
```

如需保存深度图：

```powershell
python .\scripts\capture_board_samples.py --config .\configs\board_capture.yaml --save-depth
```

## 3. 输出内容

输出目录一般位于：

```text
outputs/board_capture/<timestamp>/
```

其中包含：

- `images/`
- `depth/`（可选）
- `intrinsics.json`
- `session.json`
- `samples.csv`

## 4. 键盘操作

- `Space`：保存当前帧
- `Q` / `Esc`：退出
