from __future__ import annotations

import html
import zipfile
from pathlib import Path


OUTPUT = Path(r"D:\YOLO6D_Car\outputs\lecture_handout_work\实验数据清单_整理版.docx")


def main() -> None:
    body: list[str] = []
    body.append(p("实验数据清单", "Title"))
    body.append(p("用于 YOLO6D / Fast-Moving Object Tracking & Pose Estimation 实验结果整理", "Subtitle"))
    body.append(note("使用方式", "每完成一个 section，就把对应图片、指标表格和原始结果文件放到同一实验目录下。最终汇报或论文只需要从这份清单里挑图和表。"))

    body.append(h("1. 必须保存的图片", 1))
    body.append(table([
        ["序号", "图片名称", "必须包含的内容", "用途", "完成"],
        ["1", "训练损失曲线", "总 Loss、关键点回归 Loss（L_pt）、置信度 Loss（L_conf）随 epoch 的变化", "证明训练正常收敛", "□"],
        ["2", "验证集损失曲线", "val loss 随 epoch 的变化；必要时标注学习率衰减点", "判断是否过拟合，以及学习率衰减效果", "□"],
        ["3", "关键点预测可视化", "至少展示近/中/远距离、不同角度、不同光照下的关键点预测", "证明关键点检测稳定", "□"],
        ["4", "PnP 位姿可视化", "在图像上叠加 3D 关键点/框或坐标轴", "证明 2D-3D 几何对齐", "□"],
        ["5", "Fast-moving 连续帧可视化", "连续帧轨迹、姿态输出或对比视频截图", "展示快速运动 demo 效果", "□"],
        ["6", "Kalman 前后对比图", "raw pose 与 filtered pose 的曲线对比", "证明滤波降低抖动", "□"],
    ], widths=[650, 1700, 4100, 2500, 700]))

    body.append(h("2. 四个 section 的统一指标表", 1))
    body.append(p("说明：你现在计划做 4 个 section。下面三类表格每个 section 都要填一次，也可以先填在总表中，最后再拆成汇报用图表。"))

    body.append(h("2.1 Section 信息总表", 2))
    body.append(table([
        ["Section", "实验名称/条件", "数据集或序列", "样本数", "模型/权重", "备注"],
        ["Section 1", "", "", "", "", ""],
        ["Section 2", "", "", "", "", ""],
        ["Section 3", "", "", "", "", ""],
        ["Section 4", "", "", "", "", ""],
    ], widths=[1000, 2200, 2200, 1000, 1800, 1800]))

    body.append(h("2.2 2D Reprojection Error 结果", 2))
    body.append(p("合格重点：平均误差和中位数越低越好，同时统计阈值 < 5 px 的召回率。"))
    body.append(table([
        ["Section", "Mean / px", "Median / px", "Std / px", "Recall < 5 px / %", "样本数", "结论"],
        ["Section 1", "", "", "", "", "", ""],
        ["Section 2", "", "", "", "", "", ""],
        ["Section 3", "", "", "", "", "", ""],
        ["Section 4", "", "", "", "", "", ""],
    ], widths=[1000, 1300, 1300, 1200, 1700, 1000, 2500]))

    body.append(h("2.3 5 cm / 5° 指标结果", 2))
    body.append(p("合格重点：同时满足平移误差 < 5 cm 且旋转误差 < 5° 的比例。"))
    body.append(table([
        ["Section", "平移均值 / cm", "平移中位数 / cm", "旋转均值 / °", "旋转中位数 / °", "Recall < 5cm & 5° / %", "结论"],
        ["Section 1", "", "", "", "", "", ""],
        ["Section 2", "", "", "", "", "", ""],
        ["Section 3", "", "", "", "", "", ""],
        ["Section 4", "", "", "", "", "", ""],
    ], widths=[900, 1350, 1450, 1300, 1450, 1900, 2300]))

    body.append(h("2.4 Average Distance of Model Points / ADD 指标结果", 2))
    body.append(p("合格重点：平均模型点距离越低越好，同时统计阈值 < 10% 物体直径的召回率。"))
    body.append(table([
        ["Section", "ADD Mean", "ADD Median", "ADD Std", "物体直径 D", "阈值 0.1D", "Recall < 0.1D / %", "结论"],
        ["Section 1", "", "", "", "", "", "", ""],
        ["Section 2", "", "", "", "", "", "", ""],
        ["Section 3", "", "", "", "", "", "", ""],
        ["Section 4", "", "", "", "", "", "", ""],
    ], widths=[900, 1200, 1200, 1100, 1200, 1200, 1700, 2200]))

    body.append(h("2.5 Fast-moving Demo 可选指标", 2))
    body.append(p("如果最终 demo 要强调 fast-moving，建议额外统计下面几项。它们不是替代 6D pose 精度，而是说明系统实时性和连续性。"))
    body.append(table([
        ["Section", "FPS", "平均延迟 / ms", "最大延迟 / ms", "丢帧率 / %", "Pose Jitter", "备注"],
        ["Section 1", "", "", "", "", "", ""],
        ["Section 2", "", "", "", "", "", ""],
        ["Section 3", "", "", "", "", "", ""],
        ["Section 4", "", "", "", "", "", ""],
    ], widths=[1000, 900, 1500, 1500, 1200, 1500, 2900]))

    body.append(h("3. 每个 section 必须保留的原始文件", 1))
    for item in [
        "□ 原始图片或视频序列：images/ 或 video.mp4",
        "□ 相机时间戳：camera_timestamps.csv",
        "□ 动捕真值或同步后的真值：mocap.csv / gt_pose.csv",
        "□ 预测结果：predictions.jsonl 或 predictions.csv",
        "□ 评估指标：metrics_summary.json / metrics.csv",
        "□ 可视化结果：overlays/、plots/、demo_video.mp4",
        "□ 本次运行配置：config.yaml，包括模型权重、相机内参、外参、Kalman 参数",
    ]:
        body.append(p(item))

    body.append(h("4. 填表规范", 1))
    for item in [
        "单位必须统一：平移误差统一用 cm，旋转误差统一用 degree，重投影误差统一用 pixel。",
        "四个 section 尽量使用同一测试集或同一组测试条件，否则表格中必须写清差异。",
        "每个指标都要同时给均值和中位数；均值容易受异常值影响，中位数更能反映典型表现。",
        "如果某个 section 出现失败帧，不能只删除失败帧；需要单独统计 missed frames 或 failure rate。",
        "最终汇报建议优先展示：训练/验证损失曲线、2D reprojection error 表、5cm/5° 表、ADD 表、Kalman 前后对比图。",
    ]:
        body.append(p(item))

    files = build_docx("\n".join(body))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        OUTPUT.unlink()
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    print(OUTPUT)


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def p(text: str, style: str = "Normal") -> str:
    return f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr><w:r><w:t xml:space="preserve">{esc(text)}</w:t></w:r></w:p>'


def h(text: str, level: int) -> str:
    return p(text, f"Heading{level}")


def note(title: str, text: str) -> str:
    return (
        '<w:p><w:pPr><w:pStyle w:val="Note"/></w:pPr>'
        f'<w:r><w:rPr><w:b/></w:rPr><w:t>{esc(title)}：</w:t></w:r>'
        f'<w:r><w:t>{esc(text)}</w:t></w:r></w:p>'
    )


def table(rows: list[list[str]], widths: list[int]) -> str:
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    xml = [
        '<w:tbl>',
        '<w:tblPr><w:tblW w:w="0" w:type="auto"/><w:tblBorders>'
        '<w:top w:val="single" w:sz="6" w:color="94A3B8"/>'
        '<w:left w:val="single" w:sz="6" w:color="94A3B8"/>'
        '<w:bottom w:val="single" w:sz="6" w:color="94A3B8"/>'
        '<w:right w:val="single" w:sz="6" w:color="94A3B8"/>'
        '<w:insideH w:val="single" w:sz="4" w:color="CBD5E1"/>'
        '<w:insideV w:val="single" w:sz="4" w:color="CBD5E1"/>'
        '</w:tblBorders><w:tblCellMar>'
        '<w:top w:w="90" w:type="dxa"/><w:left w:w="90" w:type="dxa"/>'
        '<w:bottom w:w="90" w:type="dxa"/><w:right w:w="90" w:type="dxa"/>'
        '</w:tblCellMar></w:tblPr>',
        f"<w:tblGrid>{grid}</w:tblGrid>",
    ]
    for r, row in enumerate(rows):
        xml.append("<w:tr>")
        for c, cell in enumerate(row):
            fill = "E0F2FE" if r == 0 else "FFFFFF"
            bold = "<w:b/>" if r == 0 else ""
            xml.append(
                f'<w:tc><w:tcPr><w:tcW w:w="{widths[c]}" w:type="dxa"/><w:shd w:fill="{fill}"/></w:tcPr>'
                f'<w:p><w:pPr><w:spacing w:after="0"/></w:pPr><w:r><w:rPr>{bold}<w:rFonts w:eastAsia="Microsoft YaHei" w:ascii="Calibri"/><w:sz w:val="18"/></w:rPr>'
                f'<w:t xml:space="preserve">{esc(cell)}</w:t></w:r></w:p></w:tc>'
            )
        xml.append("</w:tr>")
    xml.append("</w:tbl>")
    xml.append('<w:p><w:pPr><w:spacing w:after="120"/></w:pPr></w:p>')
    return "\n".join(xml)


def build_docx(body_xml: str) -> dict[str, bytes]:
    return {
        "[Content_Types].xml": b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>''',
        "_rels/.rels": b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>''',
        "word/_rels/document.xml.rels": b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>''',
        "word/styles.xml": styles_xml().encode("utf-8"),
        "word/document.xml": document_xml(body_xml).encode("utf-8"),
    }


def document_xml(body_xml: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body>{body_xml}
<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="900" w:right="720" w:bottom="900" w:left="720" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>
</w:body></w:document>'''


def styles_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:rFonts w:eastAsia="Microsoft YaHei" w:ascii="Calibri"/><w:sz w:val="21"/></w:rPr><w:pPr><w:spacing w:after="120" w:line="300" w:lineRule="auto"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:color w:val="0F172A"/><w:sz w:val="38"/></w:rPr><w:pPr><w:spacing w:after="120"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/><w:rPr><w:color w:val="475569"/><w:sz w:val="22"/></w:rPr><w:pPr><w:spacing w:after="200"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:color w:val="075985"/><w:sz w:val="28"/></w:rPr><w:pPr><w:spacing w:before="220" w:after="100"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:color w:val="0F766E"/><w:sz w:val="23"/></w:rPr><w:pPr><w:spacing w:before="160" w:after="80"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="Note"><w:name w:val="Note"/><w:basedOn w:val="Normal"/><w:pPr><w:shd w:fill="ECFEFF"/><w:spacing w:before="80" w:after="160"/></w:pPr><w:rPr><w:color w:val="155E75"/></w:rPr></w:style>
</w:styles>'''


if __name__ == "__main__":
    main()
