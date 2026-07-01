# 海康相机现场参数预设

本文档用于海康 MV-CS016-10UC 在 YOLO6D_Car 项目中的现场调参。当前建议分成两类：标定用自动曝光，高速采集用固定曝光。

## 1. 先看画面，不保存

这条命令用于先找画面、调焦、确认棋盘格或小车是否清楚：

```powershell
python .\scripts\test_hikvision_camera.py --mvs-python-path "E:\MVS\Development\Samples\Python\MvImport" --frame-rate 30 --exposure-auto continuous --auto-exposure-upper-us 12000 --gain-auto continuous --auto-gain-upper-db 17 --preview-gain 1.8 --preview-gamma 1.3 --pixel-format BGR8
```

判断标准：

- 棋盘格黑白边界要清楚，角点不要糊。
- 车身主体要能看清，不要只靠显示增强勉强看到。
- 右侧窗户或强光区域过曝没关系，但棋盘格和小车不要放在过曝区域。
- 如果 `raw_mean` 长期低于 30，真实保存图像偏暗；如果 `gain` 长期到 17 dB，噪点会明显增加。

## 2. 标定参数

标定板不高速运动，所以允许使用自动曝光和自动增益。当前 8mm 标定命令：

```powershell
python .\scripts\calibrate_hik_camera.py --config .\configs\calibration_hik_8mm.yaml --paths-config .\configs\paths_laptop.yaml --mode capture_and_calibrate
```

6mm 标定命令：

```powershell
python .\scripts\calibrate_hik_camera.py --config .\configs\calibration_hik_6mm.yaml --paths-config .\configs\paths_laptop.yaml --mode capture_and_calibrate
```

标定时把棋盘格放在均匀光照区域，尽量避开右侧强光窗口。棋盘格需要覆盖中心、四角、近距离、远距离、倾斜和旋转姿态。

## 3. Fast moving 首选采集参数

高速运动建议使用固定曝光和固定增益。首选参数是 `60 fps + 5000 us + 6 dB`：

```powershell
python .\scripts\collect_hikvision_sequence.py --output-dir D:\CaptureData\<session> --duration 30 --fps 60 --exposure-us 5000 --gain 6 --width 1440 --height 1080 --preview --preview-before-start --preview-gain 2.0 --preview-gamma 1.4 --mvs-python-path "E:\MVS\Development\Samples\Python\MvImport" --pixel-format BGR8
```

这套参数适合先正式试采。它的目标不是让画面特别亮，而是让小车运动时边缘不明显拖影。

## 4. 偏暗备选参数

如果小车明显偏暗，但还没有明显拖影，可以改成：

```powershell
python .\scripts\collect_hikvision_sequence.py --output-dir D:\CaptureData\<session> --duration 30 --fps 60 --exposure-us 7000 --gain 8 --width 1440 --height 1080 --preview --preview-before-start --preview-gain 1.8 --preview-gamma 1.3 --mvs-python-path "E:\MVS\Development\Samples\Python\MvImport" --pixel-format BGR8
```

注意：这套参数会更亮，但噪点和拖影风险更高。若小车速度很快，不建议继续往上加曝光。

## 5. 高速防拖影参数

如果小车跑起来边缘糊、轮子和车身拖影明显，改成：

```powershell
python .\scripts\collect_hikvision_sequence.py --output-dir D:\CaptureData\<session> --duration 30 --fps 60 --exposure-us 3500 --gain 8 --width 1440 --height 1080 --preview --preview-before-start --preview-gain 2.2 --preview-gamma 1.5 --mvs-python-path "E:\MVS\Development\Samples\Python\MvImport" --pixel-format BGR8
```

这套参数需要更多现场补光，否则画面会更暗。

## 6. 现场调参顺序

1. 先运行预览命令，确认构图、对焦、棋盘格或小车位置。
2. 标定阶段用自动曝光和自动增益。
3. Fast moving 正式采集阶段从 `5000 us / 6 dB / 60 fps` 开始。
4. 如果暗，优先加灯；其次用 `7000 us / 8 dB`。
5. 如果糊，优先降曝光到 `3500 us`；然后加灯，而不是盲目加增益。
6. 每次换镜头、重新对焦、明显改变安装姿态，都要重新做内参；如果相机刚体或安装姿态变化，还要重新做外参。
