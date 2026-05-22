from __future__ import annotations

import html
import os
import re
import shutil
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


@dataclass
class Slide:
    index: int
    title: str
    subtitle: str
    text_lines: list[str]
    image_path: Path


@dataclass
class SourceSection:
    title: str
    paragraphs: list[str]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    work_dir = root / "outputs" / "lecture_handout_work"
    pptx_path = Path(r"C:\Users\25701\Desktop\YOLOv8Pose_FastMoving_1hour_Beautified.pptx")
    docx_path = Path(r"C:\Users\25701\Desktop\YOLO6D_FastMoving_详细公式版_扩展完整版讲义.docx")
    slides_dir = work_dir / "slides"
    output_path = root / "outputs" / "lecture_handout_work" / "YOLO6D_FastMoving_1hour_演讲讲义整合版.docx"

    slides = read_pptx_slides(pptx_path, slides_dir)
    sections = read_docx_sections(docx_path)
    section_lookup = build_section_lookup(sections)
    copied_images = copy_slide_images(slides, work_dir / "docx_images")

    files = build_docx_files(
        slides=slides,
        section_lookup=section_lookup,
        copied_images=copied_images,
        output_path=output_path,
    )
    write_docx(output_path, files)
    print(output_path)


def read_pptx_slides(pptx_path: Path, slides_dir: Path) -> list[Slide]:
    slides: list[Slide] = []
    with zipfile.ZipFile(pptx_path) as zf:
        slide_names = sorted(
            [name for name in zf.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)],
            key=lambda name: int(re.search(r"slide(\d+)\.xml", name).group(1)),
        )
        for i, name in enumerate(slide_names, start=1):
            root = ET.fromstring(zf.read(name))
            raw_lines = [node.text or "" for node in root.findall(".//a:t", NS)]
            lines = clean_slide_lines(raw_lines)
            title = pick_slide_title(lines, i)
            subtitle = pick_slide_subtitle(lines, title)
            image_path = slides_dir / f"slide_{i:02d}.png"
            slides.append(Slide(i, title, subtitle, lines, image_path))
    return slides


def clean_slide_lines(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    for line in lines:
        text = re.sub(r"\s+", " ", line).strip()
        if not text:
            continue
        if re.fullmatch(r"\d{2}\s*/\s*\d{2}", text):
            continue
        if text in {"YOLOv8-Pose · PnP · Kalman Filter · Fast-moving 6D Pose"}:
            continue
        cleaned.append(text)
    return cleaned


def pick_slide_title(lines: list[str], index: int) -> str:
    skip = {"1", "2", "3", "4", "5", "6", "7"}
    for line in lines:
        if index == 1:
            return lines[0] if lines else "封面"
        if line in skip:
            continue
        if re.fullmatch(r"\d+(\.\d+)?", line):
            continue
        return line
    return f"Slide {index}"


def pick_slide_subtitle(lines: list[str], title: str) -> str:
    for line in lines:
        if line == title:
            continue
        if re.fullmatch(r"\d+(\.\d+)?", line):
            continue
        if line in {"1", "2", "3", "4", "5", "6", "7"}:
            continue
        return line
    return ""


def read_docx_sections(docx_path: Path) -> list[SourceSection]:
    with zipfile.ZipFile(docx_path) as zf:
        document = ET.fromstring(zf.read("word/document.xml"))
        styles = read_docx_style_names(zf)
    sections: list[SourceSection] = []
    current = SourceSection("讲义开头材料", [])
    sections.append(current)
    for paragraph in document.findall(".//w:p", NS):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", NS)).strip()
        text = re.sub(r"\s+", " ", text)
        if not text:
            continue
        style_id = ""
        p_style = paragraph.find("./w:pPr/w:pStyle", NS)
        if p_style is not None:
            style_id = p_style.attrib.get(f"{{{NS['w']}}}val", "")
        style_name = styles.get(style_id, style_id)
        is_heading = "标题" in style_name or "Heading" in style_name or style_id.lower().startswith("heading")
        if is_heading:
            current = SourceSection(text, [])
            sections.append(current)
        else:
            current.paragraphs.append(text)
    return sections


def read_docx_style_names(zf: zipfile.ZipFile) -> dict[str, str]:
    if "word/styles.xml" not in zf.namelist():
        return {}
    styles_root = ET.fromstring(zf.read("word/styles.xml"))
    styles: dict[str, str] = {}
    for style in styles_root.findall(".//w:style", NS):
        style_id = style.attrib.get(f"{{{NS['w']}}}styleId", "")
        name_node = style.find("./w:name", NS)
        if style_id and name_node is not None:
            styles[style_id] = name_node.attrib.get(f"{{{NS['w']}}}val", style_id)
    return styles


def build_section_lookup(sections: list[SourceSection]) -> dict[int, list[str]]:
    all_text = []
    for section in sections:
        if section.paragraphs:
            all_text.append((section.title, section.paragraphs[:]))

    mapping: dict[int, list[str]] = {i: [] for i in range(1, 39)}
    keywords = {
        4: ["Detection", "Tracking", "Pose Estimation"],
        5: ["2D Box", "6D Pose"],
        8: ["图像在神经网络", "RGB"],
        9: ["CNN", "卷积", "Feature Map"],
        10: ["YOLOv8-Pose", "Backbone", "Neck"],
        11: ["YOLOv8 Detect", "YOLOv8 Pose"],
        12: ["自定义", "关键点"],
        13: ["标签格式", "visibility"],
        15: ["2D", "3D Model"],
        16: ["PnP", "输入", "输出"],
        17: ["投影公式", "相机投影"],
        18: ["相机内参", "K"],
        19: ["重投影误差"],
        21: ["坐标系"],
        22: ["齐次变换"],
        23: ["链式变换", "动捕真值"],
        24: ["相机刚体", "光学坐标"],
        26: ["Motion Blur", "运动模糊"],
        27: ["视角", "遮挡", "尺度"],
        28: ["关键点抖动", "位姿抖动"],
        29: ["mAP"],
        30: ["误差传导"],
        32: ["Kalman", "直觉"],
        33: ["Kalman", "公式"],
        34: ["2D 层", "6D 位姿层"],
        36: ["Ground Truth", "动捕"],
        37: ["在线阶段", "Pipeline"],
        38: ["总结"],
    }

    used_titles: set[str] = set()
    for slide_idx, words in keywords.items():
        chunks: list[str] = []
        for title, paras in all_text:
            haystack = title + " " + " ".join(paras[:4])
            if any(word in haystack for word in words) and title not in used_titles:
                used_titles.add(title)
                chunks.append(f"【{title}】")
                chunks.extend(paras[:8])
            if len(chunks) >= 12:
                break
        mapping[slide_idx] = chunks[:12]

    # Add compact general background to chapter divider slides.
    for slide_idx in [1, 2, 3, 7, 14, 20, 25, 31, 35]:
        if not mapping[slide_idx]:
            mapping[slide_idx] = [
                "本页是章节过渡页，主要任务是提醒听众当前讲解位置，不需要展开公式。",
                "如果时间紧，本页只讲一句过渡话；如果时间充足，可以补充为什么下一章和上一章相连。",
            ]
    return mapping


def copy_slide_images(slides: list[Slide], image_dir: Path) -> dict[int, Path]:
    if image_dir.exists():
        shutil.rmtree(image_dir)
    image_dir.mkdir(parents=True, exist_ok=True)
    copied: dict[int, Path] = {}
    for slide in slides:
        target = image_dir / f"slide_{slide.index:02d}.png"
        shutil.copy2(slide.image_path, target)
        copied[slide.index] = target
    return copied


def build_docx_files(
    slides: list[Slide],
    section_lookup: dict[int, list[str]],
    copied_images: dict[int, Path],
    output_path: Path,
) -> dict[str, bytes]:
    media_files: dict[str, bytes] = {}
    image_rels = []
    body_parts: list[str] = []

    body_parts.append(p("YOLO6D Fast-Moving 1小时演讲讲义整合版", style="Title"))
    body_parts.append(p("结构：PPT缩略图 → 现场讲述话术 → 重点必讲原理 → 备讲材料。目标是在 60 分钟内讲清 YOLOv8-Pose、PnP、坐标系与 Kalman 的主线。", style="Subtitle"))
    body_parts.append(callout("使用方式", "上台时只看“现场讲述”和“重点必讲”；被追问或时间富余时再看“备讲/可跳过”。所有“原讲义扩展材料”来自你提供的 Word 讲义，已按 PPT 顺序重新分配。", "info"))
    body_parts.append(heading("60分钟时间分配", 1))
    for text in [
        "0-5 min：路线与问题定义。",
        "5-18 min：YOLOv8-Pose 前端与关键点标签。",
        "18-34 min：PnP、相机内参、重投影误差。",
        "34-43 min：坐标系与动捕真值转换。",
        "43-53 min：Fast-moving 难点与误差传导。",
        "53-60 min：Kalman、系统 Pipeline 与总结。",
    ]:
        body_parts.append(bullet(text))

    for slide in slides:
        rel_id = f"rId{slide.index}"
        image_name = f"image{slide.index:03d}.png"
        media_files[f"word/media/{image_name}"] = copied_images[slide.index].read_bytes()
        image_rels.append((rel_id, f"media/{image_name}"))

        body_parts.append(page_break())
        body_parts.append(heading(f"第 {slide.index:02d} 页：{slide.title}", 1))
        if slide.subtitle:
            body_parts.append(p(slide.subtitle, style="SlideSubtitle"))
        body_parts.append(image_paragraph(rel_id, image_name, width_in=5.9))

        meta = slide_plan(slide.index, slide.title, slide.subtitle)
        body_parts.append(label("建议用时", meta["time"]))
        body_parts.append(heading("现场讲述内容", 2))
        for item in meta["talk"]:
            body_parts.append(bullet(item))
        body_parts.append(heading("重点必讲原理", 2))
        for item in meta["must"]:
            body_parts.append(callout("重点", item, "must"))
        body_parts.append(heading("备讲/可跳过，但需要准备", 2))
        for item in meta["backup"]:
            body_parts.append(bullet(item, style="BackupBullet"))

        source_chunks = section_lookup.get(slide.index, [])
        body_parts.append(heading("原 Word 讲义扩展材料", 2))
        if source_chunks:
            for chunk in source_chunks[:12]:
                if chunk.startswith("【"):
                    body_parts.append(p(chunk, style="SourceHeading"))
                else:
                    body_parts.append(p(chunk, style="SourceBody"))
        else:
            body_parts.append(p("本页在原 Word 中没有明显一一对应的小节，按 PPT 现场话术讲即可。", style="SourceBody"))

    body_xml = "\n".join(body_parts)
    files: dict[str, bytes] = {}
    files["[Content_Types].xml"] = content_types_xml(len(media_files)).encode("utf-8")
    files["_rels/.rels"] = package_rels_xml().encode("utf-8")
    files["word/_rels/document.xml.rels"] = document_rels_xml(image_rels).encode("utf-8")
    files["word/styles.xml"] = styles_xml().encode("utf-8")
    files["word/numbering.xml"] = numbering_xml().encode("utf-8")
    files["word/settings.xml"] = settings_xml().encode("utf-8")
    files["word/document.xml"] = document_xml(body_xml).encode("utf-8")
    files.update(media_files)
    return files


def slide_plan(index: int, title: str, subtitle: str) -> dict[str, object]:
    defaults = {
        "time": "1.5 min",
        "talk": [
            f"先用本页标题建立问题：{title}。",
            "不要逐字念 PPT，围绕主线解释它在整个 YOLO6D pipeline 中的位置。",
            "结尾用一句话过渡到下一页。",
        ],
        "must": ["讲清这一页和“2D关键点 → PnP → 6D位姿 → 时序稳定”的主线关系。"],
        "backup": ["如果老师追问，再展开公式或实现细节；时间紧可以跳过推导。"],
    }
    plans: dict[int, dict[str, object]] = {
        1: {"time": "1 min", "talk": ["开场先说研究目标：面向 fast-moving object tracking and pose estimation。", "强调系统不是只做检测，而是要从图像输出稳定 6D 位姿。"], "must": ["YOLOv8-Pose + PnP + Kalman 是三段式结构。"], "backup": ["具体硬件、采集过程可以留到最后 Pipeline 页再讲。"]},
        2: {"time": "2 min", "talk": ["用路线图告诉听众一小时会怎么走。", "先问题定义，再网络，再几何，再动态稳定，最后落到系统。"], "must": ["让听众知道后面每一章都在回答一个问题。"], "backup": ["细节目录不用逐条读。"]},
        4: {"time": "2 min", "talk": ["区分 detection、tracking、pose estimation。", "强调 pose 比 box 多了空间位置和朝向。"], "must": ["6D = translation + rotation，不只是二维框。"], "backup": ["ID switch、轨迹管理等 tracking 细节可跳过。"]},
        5: {"time": "1.5 min", "talk": ["用无人机场景解释为什么 box 不够。", "box 只能说在图像哪里，不能说离相机多远、车头朝哪。"], "must": ["2D box 是区域，6D pose 是空间关系。"], "backup": ["可以不展开控制系统，只说为决策服务。"]},
        10: {"time": "2 min", "talk": ["把 YOLOv8-Pose 定位成前端关键点检测器。", "它输出 box、keypoints、confidence，后面才接 PnP。"], "must": ["YOLOv8-Pose 本身不直接输出最终 6D 位姿。"], "backup": ["Backbone/Neck/Head 结构只讲直觉，不细讲网络层。"]},
        12: {"time": "2 min", "talk": ["说明关键点不是只能是人体关节，也可以是小车结构点。", "强调每个点必须有固定身份，并和 3D 模型点一一对应。"], "must": ["关键点身份固定，否则 PnP 会错。"], "backup": ["具体 12 点/轮子/虚拟点设计可作为项目经历补充。"]},
        15: {"time": "2 min", "talk": ["解释同一个物理点在图像中是 2D，在模型中是 3D。", "PnP 吃的就是这些对应关系。"], "must": ["2D-3D correspondence 是 PnP 的入口。"], "backup": ["可以跳过复杂坐标系，下一章再讲。"]},
        17: {"time": "3 min", "talk": ["这是核心公式页，要慢一点。", "从 3D 点经过 R,t 和相机内参 K 投影到像素点。", "PnP 是这个投影过程的反问题。"], "must": ["s[u,v,1]^T = K[R|t][X,Y,Z,1]^T。", "K 是相机，R,t 是目标相对相机的位姿。"], "backup": ["不需要推导透视投影，只解释每一项含义。"]},
        19: {"time": "2.5 min", "talk": ["解释 PnP 为什么能求解：它找让重投影误差最小的 R,t。", "把预测关键点和投影关键点之间的像素距离作为误差。"], "must": ["重投影误差越小，说明这组位姿越能解释观测。"], "backup": ["优化算法细节和 solvePnP 变体可以备讲。"]},
        21: {"time": "2 min", "talk": ["坐标系页要先定符号，不然老师最容易追问。", "明确 W、C、Bc、Bo、O 分别是什么。"], "must": ["动捕给世界坐标，PnP 输出相机坐标，必须统一。"], "backup": ["不要一开始就写复杂链式矩阵，先讲每个坐标系职责。"]},
        23: {"time": "3 min", "talk": ["讲链式变换：从动捕刚体到模型，再从世界到相机。", "重点是矩阵乘法顺序不能错。"], "must": ["T_C^O 才是能和图像/PnP 对齐的位姿。"], "backup": ["相机刚体外参和小车刚体外参的具体标定过程可作为追问材料。"]},
        26: {"time": "2 min", "talk": ["fast-moving 的第一类问题是运动模糊。", "曝光期间目标移动，边缘和角点质量下降。"], "must": ["模糊先破坏图像特征，再传到关键点和 PnP。"], "backup": ["可以补充全局快门、曝光、补光之间的取舍。"]},
        28: {"time": "2.5 min", "talk": ["讲清关键点抖动为什么会放大成位姿抖动。", "单点几像素误差会破坏整体几何结构。"], "must": ["Delta p 会导致 Delta R, Delta t。"], "backup": ["可以不推导误差传播雅可比，只讲直觉。"]},
        29: {"time": "2 min", "talk": ["这是防守页：解释为什么训练 mAP 高还不代表 demo 稳。", "mAP 不是 pose jitter 和 tracking continuity 指标。"], "must": ["评价 fast-moving 需要看动态稳定性，不只看检测分数。"], "backup": ["可以准备 ADD、rotation error、translation error、jitter 等指标名。"]},
        32: {"time": "2 min", "talk": ["用一句话讲 Kalman：上一帧帮助预测下一帧。", "当前观测和历史运动趋势融合。"], "must": ["Prediction + Measurement + Update。"], "backup": ["矩阵公式留到下一页。"]},
        33: {"time": "3 min", "talk": ["公式页只解释符号，不做完整推导。", "x 是状态，F 是运动模型，z 是观测，K 是信任权重。"], "must": ["Kalman gain 决定更信预测还是更信观测。"], "backup": ["Q/R 噪声协方差如果被追问再展开。"]},
        34: {"time": "2 min", "talk": ["比较滤 2D 和滤 6D。", "第一版 baseline 推荐先滤 PnP 后的 6D 位姿，因为解释清楚、实现直接。"], "must": ["Kalman 可以放在不同层级，但工程上先选最稳的 baseline。"], "backup": ["2D keypoint filtering 的可见性处理可以备讲。"]},
        36: {"time": "2 min", "talk": ["讲训练阶段闭环：图像、动捕、标定、自动标签、训练。", "动捕既是老师，也是评估裁判。"], "must": ["标定把动捕世界和相机图像对齐。"], "backup": ["具体采集 session、光照、背景变化可作为项目工作量补充。"]},
        37: {"time": "2 min", "talk": ["讲在线阶段：RGB 帧进来，YOLO 给关键点，PnP 给位姿，Kalman 稳定输出。", "最后落到 FPS、latency、stability。"], "must": ["前端、几何后端、时序后端分工清楚。"], "backup": ["实时系统代码结构可以在问答时展开。"]},
        38: {"time": "2 min", "talk": ["用三句话收束整场。", "最后抛出讨论问题：box 很准，为什么 pose 仍然不稳？"], "must": ["YOLOv8-Pose 是 2D keypoint；PnP 求 R,t；fast-moving 难在 temporal stability。"], "backup": ["问答时回到重投影误差和 Kalman。"]},
    }
    return plans.get(index, defaults)


def p(text: str, style: str = "Normal") -> str:
    return f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>{run(text)}</w:p>'


def heading(text: str, level: int) -> str:
    return p(text, style=f"Heading{level}")


def bullet(text: str, style: str = "ListBullet") -> str:
    return p(text, style=style)


def label(label_text: str, value: str) -> str:
    return f'<w:p><w:pPr><w:pStyle w:val="Meta"/></w:pPr>{run(label_text + "：", bold=True)}{run(value)}</w:p>'


def callout(label_text: str, text: str, kind: str) -> str:
    style = "CalloutMust" if kind == "must" else "CalloutInfo"
    return f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>{run(label_text + "：", bold=True)}{run(text)}</w:p>'


def run(text: str, bold: bool = False) -> str:
    rpr = "<w:rPr><w:b/></w:rPr>" if bold else ""
    return f"<w:r>{rpr}<w:t xml:space=\"preserve\">{html.escape(text)}</w:t></w:r>"


def page_break() -> str:
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def image_paragraph(rel_id: str, name: str, width_in: float) -> str:
    width_px, height_px = png_size(Path(name))
    # Fallback to slide aspect ratio if the media name is not directly readable here.
    if width_px == 0:
        width_px, height_px = 1280, 720
    cx = int(width_in * 914400)
    cy = int(cx * height_px / width_px)
    return f"""
<w:p>
  <w:pPr><w:jc w:val="center"/></w:pPr>
  <w:r>
    <w:drawing>
      <wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" distT="0" distB="0" distL="0" distR="0">
        <wp:extent cx="{cx}" cy="{cy}"/>
        <wp:docPr id="{rel_id[3:]}" name="{html.escape(name)}"/>
        <a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
          <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
            <pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
              <pic:nvPicPr><pic:cNvPr id="0" name="{html.escape(name)}"/><pic:cNvPicPr/></pic:nvPicPr>
              <pic:blipFill><a:blip r:embed="{rel_id}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
              <pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>
            </pic:pic>
          </a:graphicData>
        </a:graphic>
      </wp:inline>
    </w:drawing>
  </w:r>
</w:p>"""


def png_size(path: Path) -> tuple[int, int]:
    return (1280, 720)


def document_xml(body_xml: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    {body_xml}
    <w:sectPr>
      <w:pgSz w:w="12240" w:h="15840"/>
      <w:pgMar w:top="1080" w:right="900" w:bottom="900" w:left="900" w:header="708" w:footer="708" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>"""


def styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:sz w:val="21"/></w:rPr><w:pPr><w:spacing w:after="120" w:line="300" w:lineRule="auto"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:color w:val="0B2545"/><w:sz w:val="40"/></w:rPr><w:pPr><w:spacing w:after="160"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/><w:rPr><w:color w:val="475569"/><w:sz w:val="22"/></w:rPr><w:pPr><w:spacing w:after="180"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:color w:val="1F4D78"/><w:sz w:val="30"/></w:rPr><w:pPr><w:spacing w:before="200" w:after="120"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:color w:val="2E74B5"/><w:sz w:val="24"/></w:rPr><w:pPr><w:spacing w:before="120" w:after="80"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="SlideSubtitle"><w:name w:val="Slide Subtitle"/><w:basedOn w:val="Normal"/><w:rPr><w:i/><w:color w:val="475569"/><w:sz w:val="21"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Meta"><w:name w:val="Meta"/><w:basedOn w:val="Normal"/><w:rPr><w:color w:val="7A5A00"/><w:sz w:val="20"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="ListBullet"><w:name w:val="List Bullet"/><w:basedOn w:val="Normal"/><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr><w:ind w:left="540" w:hanging="260"/><w:spacing w:after="80"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="BackupBullet"><w:name w:val="Backup Bullet"/><w:basedOn w:val="Normal"/><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr><w:ind w:left="540" w:hanging="260"/><w:spacing w:after="80"/></w:pPr><w:rPr><w:color w:val="666666"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="CalloutMust"><w:name w:val="Callout Must"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="80" w:after="100"/><w:shd w:fill="FFF4CC"/></w:pPr><w:rPr><w:color w:val="7A4A00"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="CalloutInfo"><w:name w:val="Callout Info"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="80" w:after="100"/><w:shd w:fill="E8EEF5"/></w:pPr><w:rPr><w:color w:val="1F3A5F"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="SourceHeading"><w:name w:val="Source Heading"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:color w:val="334155"/><w:sz w:val="20"/></w:rPr><w:pPr><w:spacing w:before="80" w:after="60"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="SourceBody"><w:name w:val="Source Body"/><w:basedOn w:val="Normal"/><w:rPr><w:color w:val="334155"/><w:sz w:val="19"/></w:rPr><w:pPr><w:spacing w:after="70" w:line="280" w:lineRule="auto"/></w:pPr></w:style>
</w:styles>"""


def content_types_xml(image_count: int) -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
  <Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
</Types>"""


def package_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""


def document_rels_xml(image_rels: list[tuple[str, str]]) -> str:
    rels = [
        '<Relationship Id="rStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>',
        '<Relationship Id="rNumbering" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>',
        '<Relationship Id="rSettings" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>',
    ]
    for rel_id, target in image_rels:
        rels.append(f'<Relationship Id="{rel_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="{target}"/>')
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(rels) + "</Relationships>"


def settings_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:zoom w:percent="100"/>
</w:settings>"""


def numbering_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="0">
    <w:multiLevelType w:val="singleLevel"/>
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/>
      <w:numFmt w:val="bullet"/>
      <w:lvlText w:val="•"/>
      <w:lvlJc w:val="left"/>
      <w:pPr>
        <w:tabs><w:tab w:val="num" w:pos="540"/></w:tabs>
        <w:ind w:left="540" w:hanging="260"/>
      </w:pPr>
      <w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol" w:hint="default"/></w:rPr>
    </w:lvl>
  </w:abstractNum>
  <w:num w:numId="1">
    <w:abstractNumId w:val="0"/>
  </w:num>
</w:numbering>"""


def write_docx(path: Path, files: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)


if __name__ == "__main__":
    main()
