# YOLO6D_Car 常用命令速查

本文档把采集笔记本和主机上最常用的命令集中放在一起。命令中的 `<session>`、`<date>`、`<dataset_name>`、`<run_name>` 需要按实际实验替换。

## 1. 采集笔记本基础检查

进入项目：

```powershell
cd D:\YOLO6D_Car
```

检查 Git 状态：

```powershell
git status
```

检查本地采集目录：

```powershell
Test-Path D:\CaptureData
dir D:\CaptureData
```

检查主机共享盘：

```powershell
Test-Path Z:\
Test-Path Z:\captures
dir Z:\
```

如果 `Z:\` 不存在，重新映射：

```powershell
net use Z: "\\192.168.50.250\YOLO6D_Car_Data" /user:Cryonixzz\yolo_sync <你的密码> /persistent:yes
```

## 2. 海康相机预览和调参

基础预览：

```powershell
python .\scripts\test_hikvision_camera.py --mvs-python-path "E:\MVS\Development\Samples\Python\MvImport" --frame-rate 60 --exposure-time-us 5000 --gain-db 6
```

低曝光、低增益，适合减少拖影和噪点：

```powershell
python .\scripts\test_hikvision_camera.py --mvs-python-path "E:\MVS\Development\Samples\Python\MvImport" --frame-rate 60 --exposure-time-us 4000 --gain-db 4
```

较亮预览，只改变显示亮度，不改变真实采集图：

```powershell
python .\scripts\test_hikvision_camera.py --mvs-python-path "E:\MVS\Development\Samples\Python\MvImport" --frame-rate 60 --exposure-time-us 5000 --gain-db 6 --preview-gain 2 --preview-gamma 1.4
```

自动曝光和自动增益预览：

```powershell
python .\scripts\test_hikvision_camera.py --mvs-python-path "E:\MVS\Development\Samples\Python\MvImport" --frame-rate 60 --exposure-auto continuous --auto-exposure-upper-us 8000 --gain-auto continuous --auto-gain-upper-db 12
```

## 3. 海康连续帧采集

采集前先显示预览，按键开始：

```powershell
python .\scripts\collect_hikvision_sequence.py --output-dir D:\CaptureData\<session> --duration 30 --fps 60 --exposure-us 5000 --gain 6 --width 1440 --height 1080 --preview --preview-before-start --mvs-python-path "E:\MVS\Development\Samples\Python\MvImport"
```

示例：

```powershell
python .\scripts\collect_hikvision_sequence.py --output-dir D:\CaptureData\2026-06-04_car_fast_lateral_001 --duration 30 --fps 60 --exposure-us 5000 --gain 6 --width 1440 --height 1080 --preview --preview-before-start --mvs-python-path "E:\MVS\Development\Samples\Python\MvImport"
```

采集后检查图片数量：

```powershell
dir D:\CaptureData\<session>\images
```

检查时间戳文件：

```powershell
Get-Content D:\CaptureData\<session>\camera_timestamps.csv -TotalCount 5
```

## 4. 采集质量检查

```powershell
python .\scripts\check_capture_quality.py --capture-root D:\CaptureData\<session> --output-dir D:\CaptureData\results\capture_quality\<session> --plot
```

示例：

```powershell
python .\scripts\check_capture_quality.py --capture-root D:\CaptureData\2026-06-04_car_fast_lateral_001 --output-dir D:\CaptureData\results\capture_quality\2026-06-04_car_fast_lateral_001 --plot
```

## 5. FzMotion CSV 保存建议

建议每组 session 的 CSV 放到：

```text
D:\CaptureData\FZmotion_Data\<session>.csv
```

创建目录：

```powershell
New-Item -ItemType Directory -Force -Path D:\CaptureData\FZmotion_Data
```

检查 CSV 是否存在：

```powershell
Test-Path D:\CaptureData\FZmotion_Data\<session>.csv
```

## 6. 笔记本同步到主机

先扫描，不复制：

```powershell
python .\scripts\sync_capture_batch_to_host.py --local-root D:\CaptureData --host-root Z:\captures --plan-only
```

正式同步并校验：

```powershell
python .\scripts\sync_capture_batch_to_host.py --local-root D:\CaptureData --host-root Z:\captures --verify
```

只同步某一个 session：

```powershell
python .\scripts\sync_capture_batch_to_host.py --local-root D:\CaptureData --host-root Z:\captures --session <session> --verify
```

同步小文件测试目录：

```powershell
python .\scripts\sync_capture_batch_to_host.py --local-root D:\CaptureData --host-root Z:\captures --include-test --verify
```

检查主机共享端是否收到：

```powershell
dir Z:\captures
```

## 7. 代码同步到 GitHub

查看改动：

```powershell
git status
```

查看具体差异：

```powershell
git diff
```

添加所有代码和文档改动：

```powershell
git add .
```

提交：

```powershell
git commit -m "update docs and capture workflow"
```

推送到 GitHub：

```powershell
git push
```

如果主机要拉取最新代码：

```powershell
cd D:\Research\YOLO6D_Car
git pull
```

## 8. 主机基础检查

进入主机项目：

```powershell
cd D:\Research\YOLO6D_Car
```

检查 Python：

```powershell
D:\Envs\yolo6d\python.exe --version
```

检查项目依赖和路径：

```powershell
D:\Envs\yolo6d\python.exe scripts\check_project_readiness.py --paths-config configs\paths\paths_local.yaml
```

检查数据根目录：

```powershell
dir G:\YOLO6D_Car_Data
dir G:\YOLO6D_Car_Data\captures
dir G:\YOLO6D_Car_Data\FZmotion_Data
```

## 9. 主机检查 Mocap CSV

```powershell
D:\Envs\yolo6d\python.exe scripts\check_mocap_csv.py --csv-path FZmotion_Data\raw_csv\<session>.csv --paths-config configs\paths\paths_local.yaml --camera-rigid <camera_rigid> --object-rigid <object_rigid> --output-dir results\mocap_quality\<session> --plot
```

示例：

```powershell
D:\Envs\yolo6d\python.exe scripts\check_mocap_csv.py --csv-path FZmotion_Data\raw_csv\2026-06-04_car_fast_lateral_001.csv --paths-config configs\paths\paths_local.yaml --camera-rigid hik_rigid --object-rigid car_rigid --output-dir results\mocap_quality\2026-06-04_car_fast_lateral_001 --plot
```

## 10. 主机自动打标签

```powershell
D:\Envs\yolo6d\python.exe scripts\generate_mocap_labels.py --config configs\fzmotion_fixed_camera_current_rigids_gdrive.yaml --paths-config configs\paths\paths_local.yaml --samples-dir captures\<date>\<session> --csv-path FZmotion_Data\raw_csv\<session>.csv --output-dir outputs\auto_labels\<session> --save-overlays
```

示例：

```powershell
D:\Envs\yolo6d\python.exe scripts\generate_mocap_labels.py --config configs\fzmotion_fixed_camera_current_rigids_gdrive.yaml --paths-config configs\paths\paths_local.yaml --samples-dir captures\2026-06-04\2026-06-04_car_fast_lateral_001 --csv-path FZmotion_Data\raw_csv\2026-06-04_car_fast_lateral_001.csv --output-dir outputs\auto_labels\2026-06-04_car_fast_lateral_001 --save-overlays
```

## 11. 主机可视化检查标签

```powershell
D:\Envs\yolo6d\python.exe scripts\visualize_auto_labels.py --labels-root outputs\auto_labels\<session> --images-root captures\<date>\<session>\images --paths-config configs\paths\paths_local.yaml --output-dir results\label_visualization\<session> --max-samples 100
```

## 12. 主机构建数据集

```powershell
D:\Envs\yolo6d\python.exe scripts\prepare_yolo_pose_dataset.py --paths-config configs\paths\paths_local.yaml --auto-label-dir outputs\auto_labels\<session_or_batch> --out-dir outputs\datasets\<dataset_name> --val-ratio 0.1 --seed 42 --class-name car_model --overwrite
```

## 13. 主机训练

```powershell
D:\Envs\yolo6d\python.exe scripts\train_ultralytics_pose.py --paths-config configs\paths\paths_local.yaml --dataset outputs\datasets\<dataset_name>\dataset.yaml --model yolo11n-pose.pt --epochs 150 --imgsz 640 --batch 16 --device 0 --workers 4 --project outputs\train_runs --name <run_name>
```

## 14. 主机实时推理

```powershell
D:\Envs\yolo6d\python.exe scripts\run_live_pose.py --config configs\fzmotion_fast_moving_live_gdrive.yaml --paths-config configs\paths\paths_local.yaml --model models\<model_name>_best.pt
```

保存 CSV：

```powershell
D:\Envs\yolo6d\python.exe scripts\run_live_pose.py --config configs\fzmotion_fast_moving_live_gdrive.yaml --paths-config configs\paths\paths_local.yaml --model models\<model_name>_best.pt --headless --save-csv results\live_pose_<date>.csv
```

## 15. 常见排查命令

检查 CUDA：

```powershell
D:\Envs\yolo6d\python.exe -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no cuda')"
```

检查海康 SDK 路径：

```powershell
Test-Path "E:\MVS\Development\Samples\Python\MvImport"
```

检查主机共享空间：

```powershell
Get-PSDrive Z
```

检查 Git 远程仓库：

```powershell
git remote -v
```

检查当前分支：

```powershell
git branch
```

## 16. 明天实验室最短流程

1. 进入项目：

```powershell
cd D:\YOLO6D_Car
```

2. 预览调参：

```powershell
python .\scripts\test_hikvision_camera.py --mvs-python-path "E:\MVS\Development\Samples\Python\MvImport" --frame-rate 60 --exposure-time-us 5000 --gain-db 6
```

3. 采集一组：

```powershell
python .\scripts\collect_hikvision_sequence.py --output-dir D:\CaptureData\<session> --duration 30 --fps 60 --exposure-us 5000 --gain 6 --width 1440 --height 1080 --preview --preview-before-start --mvs-python-path "E:\MVS\Development\Samples\Python\MvImport"
```

4. 保存 CSV：

```text
D:\CaptureData\FZmotion_Data\<session>.csv
```

5. 检查采集质量：

```powershell
python .\scripts\check_capture_quality.py --capture-root D:\CaptureData\<session> --output-dir D:\CaptureData\results\capture_quality\<session> --plot
```

6. 回来同步：

```powershell
python .\scripts\sync_capture_batch_to_host.py --local-root D:\CaptureData --host-root Z:\captures --plan-only
python .\scripts\sync_capture_batch_to_host.py --local-root D:\CaptureData --host-root Z:\captures --verify
```
