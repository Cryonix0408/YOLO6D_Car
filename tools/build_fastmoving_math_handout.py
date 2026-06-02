from __future__ import annotations

import html
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from build_fastmoving_clean_script import CLEAN_PLAN, fallback_plan
from build_fastmoving_handout import (
    Slide,
    content_types_xml,
    copy_slide_images,
    document_rels_xml,
    document_xml,
    heading,
    image_paragraph,
    label,
    numbering_xml,
    package_rels_xml,
    p,
    page_break,
    read_pptx_slides,
    run,
    settings_xml,
    styles_xml,
    write_docx,
)


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
}

ET.register_namespace("w", NS["w"])
ET.register_namespace("m", NS["m"])

SOURCE_DOCX = Path(r"C:\Users\25701\Desktop\YOLO6D_FastMoving_详细公式版_扩展完整版讲义.docx")
OUTPUT_NAME = "YOLO6D_FastMoving_1hour_逐字讲稿_正式公式版.docx"


@dataclass
class MathObject:
    index: int
    text: str
    xml: str


# 这些编号来自原始 Word 讲义里的 Office Math 对象顺序。
# 目的不是机械全塞进去，而是把真正适合板书的公式放到对应 PPT 页。
MATH_BOARD_BY_SLIDE: dict[int, list[int]] = {
    1: [21],
    4: [6, 7, 14],
    5: [14, 18],
    8: [29],
    9: [32, 33],
    10: [78, 79],
    11: [73, 78],
    12: [98, 99],
    13: [78, 79, 91],
    15: [104, 105, 99],
    16: [116, 117, 140],
    17: [107, 114, 115],
    18: [115],
    19: [118, 120, 121, 122, 123],
    21: [129, 130, 131, 132, 133, 134],
    22: [135, 138, 140, 144, 148],
    23: [149, 158, 161, 165, 167],
    24: [152, 155, 162, 163, 164, 166],
    26: [196],
    27: [202, 204],
    28: [124, 125, 206, 208, 209],
    29: [212, 213, 214],
    30: [201],
    32: [215, 216, 217, 218],
    33: [225, 226, 227, 228, 229, 230, 231],
    34: [215, 216, 217],
    36: [182, 183, 185, 186, 190, 191],
    37: [95, 100, 215, 230],
    38: [95, 100, 214],
}


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    work_dir = root / "outputs" / "lecture_handout_work"
    pptx_path = Path(r"C:\Users\25701\Desktop\YOLOv8Pose_FastMoving_1hour_Beautified.pptx")
    slides_dir = work_dir / "slides"
    output_path = work_dir / OUTPUT_NAME

    slides = read_pptx_slides(pptx_path, slides_dir)
    copied_images = copy_slide_images(slides, work_dir / "docx_images_math_handout")
    math_objects = extract_math_objects(SOURCE_DOCX)

    files = build_docx_files(slides, copied_images, math_objects)
    write_docx(output_path, files)
    print(output_path)


def extract_math_objects(path: Path) -> dict[int, MathObject]:
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))

    objects: dict[int, MathObject] = {}
    index = 0
    for math in root.findall(".//m:oMath", NS):
        math_text = "".join(node.text or "" for node in math.findall(".//m:t", NS)).strip()
        if not math_text:
            continue
        index += 1
        objects[index] = MathObject(index=index, text=math_text, xml=ET.tostring(math, encoding="unicode"))
    return objects


def build_docx_files(
    slides: list[Slide],
    copied_images: dict[int, Path],
    math_objects: dict[int, MathObject],
) -> dict[str, bytes]:
    media_files: dict[str, bytes] = {}
    image_rels: list[tuple[str, str]] = []
    body: list[str] = []

    body.append(p("YOLO6D Fast-Moving 1小时逐字讲稿：正式公式版", style="Title"))
    body.append(
        p(
            "这版把红框板书改成原讲义里的 Office Math 风格公式。红框内容就是建议现场板书的公式、矩阵或核心链路。",
            style="Subtitle",
        )
    )
    body.append(heading("整体逻辑审稿结论", 1))
    body.append(
        p(
            "PPT 主线总体清晰：问题定义 -> YOLOv8-Pose 二维关键点 -> PnP 几何求解 -> 坐标系与动捕真值 -> fast-moving 误差传导 -> Kalman 稳定 -> 系统 pipeline。需要现场控制节奏：动机页快讲，坐标系和 PnP 公式页慢讲，Kalman 公式页讲直觉不做完整推导。"
        )
    )

    for slide in slides:
        rel_id = f"rId{slide.index}"
        image_name = f"image{slide.index:03d}.png"
        media_files[f"word/media/{image_name}"] = copied_images[slide.index].read_bytes()
        image_rels.append((rel_id, f"media/{image_name}"))

        plan = CLEAN_PLAN.get(slide.index, fallback_plan(slide))
        body.append(page_break())
        body.append(heading(f"第 {slide.index:02d} 页：{slide.title}", 1))
        if slide.subtitle:
            body.append(p(slide.subtitle, style="SlideSubtitle"))
        body.append(image_paragraph(rel_id, image_name, width_in=5.9))
        body.append(label("建议用时", str(plan["time"])))

        body.append(heading("逐字讲稿", 2))
        body.append(p(str(plan["script"])))

        body.append(heading("红框板书：正式公式", 2))
        math_indices = MATH_BOARD_BY_SLIDE.get(slide.index, [])
        if math_indices:
            for math_index in math_indices:
                math = math_objects.get(math_index)
                if math:
                    body.append(math_box(math))
        else:
            for item in plan.get("board", []):
                body.append(text_box(str(item)))

        body.append(heading("问答备稿", 2))
        for backup in plan.get("backup", []):
            body.append(p(str(backup), style="SourceBody"))

    body_xml = "\n".join(body)
    doc_xml = document_xml(body_xml)
    if "xmlns:m=" not in doc_xml:
        doc_xml = doc_xml.replace(
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"',
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"\n'
            '            xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"',
        )

    files: dict[str, bytes] = {
        "[Content_Types].xml": content_types_xml(len(media_files)).encode("utf-8"),
        "_rels/.rels": package_rels_xml().encode("utf-8"),
        "word/_rels/document.xml.rels": document_rels_xml(image_rels).encode("utf-8"),
        "word/styles.xml": styles_xml().encode("utf-8"),
        "word/numbering.xml": numbering_xml().encode("utf-8"),
        "word/settings.xml": settings_xml().encode("utf-8"),
        "word/document.xml": doc_xml.encode("utf-8"),
    }
    files.update(media_files)
    return files


def math_box(math: MathObject) -> str:
    return f"""
<w:p>
  <w:pPr>
    <w:spacing w:before="90" w:after="90"/>
    <w:shd w:fill="FFF7ED"/>
    <w:pBdr>
      <w:top w:val="single" w:sz="12" w:space="5" w:color="DC2626"/>
      <w:left w:val="single" w:sz="12" w:space="5" w:color="DC2626"/>
      <w:bottom w:val="single" w:sz="12" w:space="5" w:color="DC2626"/>
      <w:right w:val="single" w:sz="12" w:space="5" w:color="DC2626"/>
    </w:pBdr>
  </w:pPr>
  {run("板书：", bold=True)}
  {math.xml}
</w:p>"""


def text_box(text: str) -> str:
    escaped = html.escape(text)
    return f"""
<w:p>
  <w:pPr>
    <w:spacing w:before="80" w:after="80"/>
    <w:shd w:fill="FFF7ED"/>
    <w:pBdr>
      <w:top w:val="single" w:sz="12" w:space="4" w:color="DC2626"/>
      <w:left w:val="single" w:sz="12" w:space="4" w:color="DC2626"/>
      <w:bottom w:val="single" w:sz="12" w:space="4" w:color="DC2626"/>
      <w:right w:val="single" w:sz="12" w:space="4" w:color="DC2626"/>
    </w:pBdr>
  </w:pPr>
  {run("板书：", bold=True)}
  <w:r>
    <w:rPr>
      <w:rFonts w:ascii="Cambria Math" w:hAnsi="Cambria Math" w:eastAsia="Microsoft YaHei"/>
      <w:sz w:val="22"/>
      <w:color w:val="7F1D1D"/>
    </w:rPr>
    <w:t xml:space="preserve">{escaped}</w:t>
  </w:r>
</w:p>"""


if __name__ == "__main__":
    main()
