# 离线色彩校正实验工具

## 1. 为什么需要色彩校正

Hikrobot 工业相机在实验室低照度、不同色温和不同曝光参数下，可能产生偏色、暗部噪声和通道响应不一致。老师提出的思路是利用实验室背景墙上已有的红、绿、蓝区域作为参考色，从图像中测量它们的实际颜色，再估计颜色校正参数。

本工具只用于验证这个思路是否能够改善已有图像。它不会连接相机，也不会接入正式采集、标定、YOLO、PnP 或 Kalman pipeline。

## 2. RGB 背景墙匹配思路

1. 在测试图片中分别为红、绿、蓝背景墙区域配置一个 ROI。
2. 计算各 ROI 的平均颜色。OpenCV 读取结果为 BGR 顺序。
3. 将测得颜色与配置中的 `target_rgb` 比较。
4. 估计 RGB 通道增益或 3x3 Color Correction Matrix（CCM）。
5. 将参数应用到整张图片，并比较校正前后的参考色误差。

ROI 和 `target_rgb` 默认只是占位值，必须根据实际图片修改。不要假设墙面颜色就是纯 `[255, 0, 0]`、`[0, 255, 0]`、`[0, 0, 255]`。

## 3. 色彩校正与增加进光量的区别

色彩校正只能改变相机已经记录下来的像素值，不能恢复没有被传感器记录的细节。暗部噪声、运动模糊和严重欠曝无法通过颜色矩阵凭空消除。

因此：

- 色彩校正不能替代补光灯。
- Gamma 和 HSV-V 提亮会同时放大噪声。
- 如果输入图像严重欠曝，应优先改善照明、镜头光圈、曝光和增益设置。

## 4. RGB channel gain correction

RGB channel gain 为三个颜色通道分别估计一个比例系数：

```text
corrected_rgb = observed_rgb * gain_rgb
```

该方法简单、稳定、容易解释，但只能修正全局通道比例，无法描述颜色通道之间的交叉影响。

脚本内部对 OpenCV 图像使用 BGR，因此 JSON 同时输出 `gain_bgr` 和 `gain_rgb`，避免顺序混淆。

## 5. 3x3 Color Correction Matrix

CCM 使用一个 3x3 矩阵描述 RGB 通道之间的线性映射：

```text
corrected_rgb = observed_rgb @ ccm_rgb
```

本工具使用 NumPy 最小二乘求解。红、绿、蓝三个参考色刚好可以求解 3x3 矩阵，但样本非常少，容易对噪声、ROI 误差和光照变化过拟合。若参考颜色少于三个，工具会直接报错。

更可靠的正式颜色标定通常应使用 ColorChecker 等包含更多颜色块的标准色卡。

## 6. HSV-V 与 Gamma 的区别

### Gamma correction

Gamma 是非线性亮度变换。配置中 `gamma < 1` 会提升中间亮度，但也可能放大暗部噪声。

### HSV-V brightness enhancement

HSV-V 只调整 HSV 色彩空间中的亮度通道。它适合快速观察提亮效果，但不是严格的颜色恢复方法。

不能把 HSV-V 提亮后的视觉效果直接当作真实颜色还原结果。

## 7. 如何拍摄测试图

建议：

1. 图像中同时包含红、绿、蓝背景墙区域。
2. 三个 ROI 内尽量只包含对应颜色，不要包含黑色网格、反光、高光或阴影边界。
3. 保持曝光、增益、Gamma、白平衡参数记录完整。
4. 同时采集正常照明和低照度测试图。
5. 不要使用本工具处理正式标定图像，除非独立验证其重投影误差确实更低。

## 8. 修改 ROI

配置文件：

```text
configs/color_correction/rgb_wall_reference.yaml
```

每个 ROI 使用：

```yaml
xywh: [x, y, width, height]
```

坐标原点位于图像左上角。建议先运行 `--save-debug`，查看生成的 `debug/*_roi_overlay.jpg`，确认框选位置正确。

## 9. 修改 target_rgb

`target_rgb` 表示希望参考区域匹配到的目标 RGB 值。建议优先使用：

1. 老师指定的目标值；
2. 标准照明下测得的墙面参考值；
3. 色度计或标准色卡测量值。

不要仅凭肉眼把目标设为纯色极值。

## 10. 运行方法

### 配置检查

```powershell
python scripts\test_color_correction.py `
  --config configs\color_correction\rgb_wall_reference.yaml `
  --output-dir D:\CaptureData\outputs\color_correction\dryrun_001 `
  --dry-run
```

### 单图实验

```powershell
python scripts\test_color_correction.py `
  --input D:\CaptureData\color_test\hik_dark_001.jpg `
  --config configs\color_correction\rgb_wall_reference.yaml `
  --output-dir D:\CaptureData\outputs\color_correction\test_001 `
  --save-debug
```

### 批量实验

```powershell
python scripts\test_color_correction.py `
  --input-dir D:\CaptureData\color_test `
  --config configs\color_correction\rgb_wall_reference.yaml `
  --output-dir D:\CaptureData\outputs\color_correction\batch_001 `
  --max-images 10 `
  --save-debug
```

## 11. 输出内容

```text
output_dir/
├── corrected/
│   ├── xxx_original.jpg
│   ├── xxx_gamma.jpg
│   ├── xxx_hsv_v.jpg
│   ├── xxx_rgb_gain.jpg
│   └── xxx_ccm.jpg
├── debug/
│   ├── xxx_roi_overlay.jpg
│   ├── xxx_comparison_canvas.jpg
│   └── xxx_color_patches.jpg
├── color_correction_params.json
├── color_correction_summary.csv
└── color_correction_report.md
```

JSON 中会明确记录图像为 BGR、目标为 RGB、CCM 为 RGB 行向量矩阵。CSV 和 Markdown 报告包含每个参考色校正前后的 L2 误差与误差下降百分比。

## 12. 如何判断是否值得接入正式 pipeline

至少满足以下条件后，才值得讨论正式接入：

1. 多个 session 中，校正后的颜色误差稳定下降。
2. YOLO 检测和关键点精度在独立测试集上提升。
3. 暗部噪声和运动模糊没有明显恶化。
4. 不同距离、光照和视角下参数仍具有稳定性。
5. PnP 和重投影误差没有变差。

即使实验有效，也应优先考虑把固定参数写入独立预处理配置，而不是直接修改原始采集图像。

## 13. 当前局限

- 只有红、绿、蓝三个参考色，颜色覆盖不足。
- 三点 CCM 容易过拟合。
- 暗部噪声无法凭空恢复。
- 无法替代补光和合理曝光。
- 不应直接用于标定图像，除非独立验证重投影误差更好。
- 对 YOLO 训练和 Fast-Moving 场景是否有收益，仍需实验验证。

