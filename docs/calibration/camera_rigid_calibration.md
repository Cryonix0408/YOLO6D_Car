# 相机刚体外参标定

这个流程用于求解：

- `T_camera_rigid_to_optical`
- `T_board_rigid_to_board_visual`

脚本入口：
[solve_camera_rigid_to_optical.py](../scripts/solve_camera_rigid_to_optical.py)

## 1. 需要准备的东西

- 一组标定板采集目录：
  `outputs/board_capture/<session>`
- 该次采集对应的 FzMotion CSV
- 正确的标定板参数：
  - `markers-x`
  - `markers-y`
  - `marker-length-mm`
  - `marker-separation-mm`
  - `dictionary`

## 2. 采集建议

- 每个姿态静止 1 到 2 秒
- 覆盖近、中、远距离
- 覆盖上下左右和倾斜视角
- 尽量保证每张图都能看到足够多的 ArUco marker

## 3. 求解命令示例

```powershell
python .\scripts\solve_camera_rigid_to_optical.py `
  --config .\configs\fzmotion_fixed_camera_current_rigids.yaml `
  --samples-dir .\outputs\board_capture\<board_session> `
  --board-rigid-body Rigid2 `
  --markers-x 5 `
  --markers-y 7 `
  --marker-length-mm 28 `
  --marker-separation-mm 12 `
  --dictionary DICT_6X6_250
```

## 4. 输出结果

通常会生成：

- `outputs/calibration/*.json`

重点看：

- `T_camera_rigid_to_optical`
- 优化是否成功
- `num_used_samples`

## 5. 下一步

求出结果后，不要直接全量重打标签。  
建议先选一个 session 做打标签抽查，确认 overlay 正常后再批量处理。
