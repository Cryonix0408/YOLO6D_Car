from __future__ import annotations

from pathlib import Path

import build_fastmoving_handout_board_version as board
from build_fastmoving_handout import (
    build_section_lookup,
    copy_slide_images,
    read_docx_sections,
    read_pptx_slides,
    write_docx,
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    work_dir = root / "outputs" / "lecture_handout_work"
    pptx_path = Path(r"C:\Users\25701\Desktop\YOLOv8Pose_FastMoving_1hour_Beautified.pptx")
    docx_path = Path(r"C:\Users\25701\Desktop\YOLO6D_FastMoving_详细公式版_扩展完整版讲义.docx")
    slides_dir = work_dir / "slides"
    output_path = work_dir / "YOLO6D_FastMoving_1hour_逐字讲稿_板书公式版.docx"

    slides = read_pptx_slides(pptx_path, slides_dir)
    sections = read_docx_sections(docx_path)
    section_lookup = build_section_lookup(sections)
    copied_images = copy_slide_images(slides, work_dir / "docx_images_reading_script")

    original_verbose_plan = board.verbose_plan

    def direct_plan(slide):
        plan = original_verbose_plan(slide)
        return {
            "time": plan["time"],
            "script": [to_direct_reading(paragraph, slide.index) for paragraph in plan["script"]],
            "must": [to_direct_principle(paragraph) for paragraph in plan["must"]],
            "backup": [to_direct_backup(paragraph) for paragraph in plan["backup"]],
        }

    board.verbose_plan = direct_plan
    try:
        files = board.build_docx_files(slides, section_lookup, copied_images)
    finally:
        board.verbose_plan = original_verbose_plan

    document_xml = files["word/document.xml"].decode("utf-8")
    document_xml = document_xml.replace(
        "YOLO6D Fast-Moving 1小时长文讲稿与板书公式版",
        "YOLO6D Fast-Moving 1小时逐字讲稿与板书公式版",
    )
    document_xml = document_xml.replace(
        "这一版按演讲现场使用来写：每页先看 PPT 缩略图，再给出可以直接讲的大段话，随后列出黑板/白板上可以直接写的公式和讲解顺序。",
        "这一版是可直接照读的演讲稿：每页先放 PPT 缩略图，然后给出完整讲稿，再列出黑板/白板上可以直接写的公式。",
    )
    document_xml = document_xml.replace("现场长文讲稿", "逐字讲稿")
    document_xml = document_xml.replace("备讲可跳过，但需要准备", "问答备稿")
    document_xml = document_xml.replace(
        "使用建议：正式讲的时候，不需要把每一句都念完。你可以先读“逐字讲稿”形成自己的语言，再把“板书公式”抄到草稿纸上练两遍。被老师追问时，再看“原讲义扩展材料”。",
        "使用方式：正式讲的时候，我按照“逐字讲稿”建立完整表达，再把“板书公式”抄到草稿纸上练两遍。被老师追问时，我再回到“原讲义扩展材料”补充细节。",
    )
    document_xml = document_xml.replace(
        "这份讲义里的“重点必讲”是你上台一定要说出口的原理；“备讲可跳过”是你要准备但不一定主动展开的内容。",
        "这份讲义里的“重点必讲”是我上台一定要说出口的原理；“问答备稿”是我需要准备但不一定主动展开的内容。",
    )
    document_xml = document_xml.replace("你可以按顺序讲：", "我按顺序展开：")
    document_xml = document_xml.replace("你需要反复记住：", "我需要反复记住：")
    document_xml = document_xml.replace("你能现场写、现场解释", "我能现场写、现场解释")

    # 最后一层扫尾：原 Word 扩展材料里可能还残留“你可以/你需要/可以说”
    # 这种备课提示语。这里统一改成能直接读出口的讲稿语气。
    final_cleanup = {
        "你可以先读“逐字讲稿”形成自己的语言": "我会先通读“逐字讲稿”，形成完整讲述语感",
        "你可以按顺序讲：": "我按顺序展开：",
        "讲的时候可以": "这里我会",
        "建议讲": "这里我讲",
        "你可以": "我会",
        "你需要": "我需要",
        "你要": "我要",
        "我可以说：": "这里说明：",
        "我可以说": "这里说明",
        "可以说：": "也就是说：",
        "可以说": "也就是",
    }
    for old, new in final_cleanup.items():
        document_xml = document_xml.replace(old, new)
    files["word/document.xml"] = document_xml.encode("utf-8")

    write_docx(output_path, files)
    print(output_path)


def to_direct_reading(text: str, slide_index: int) -> str:
    text = text.strip()
    replacements = {
        "你可以先": "我先",
        "你可以把": "我把",
        "你可以用": "我用",
        "你可以说：": "我在这里说明：",
        "你可以说": "我在这里说明",
        "讲的时候可以这样说：": "我会这样展开：",
        "你可以按": "我按",
        "讲的时候可以": "我会",
        "讲的时候": "这一页",
        "这一页要": "这一页我需要",
        "这里要": "这里我需要",
        "你讲的时候": "我讲到这里时",
        "听众": "各位老师",
        "让他们记住": "我希望大家记住",
        "不要急着": "我不会急着",
        "不要只": "我不能只",
        "不要在": "我不会在",
        "后面才": "后面再",
        "老师如果追问": "如果老师追问",
        "你的项目": "本项目",
        "你之前": "前期实验中",
        "你现在": "现在",
        "你需要": "我需要",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = text.replace("这一页我需要强调", "这一页我重点强调")
    text = text.replace("这一页我需要解释", "这一页我解释")
    text = text.replace("这一页我需要把", "这一页我把")

    if slide_index == 1:
        return "各位老师好，我今天汇报的题目是基于 YOLOv8-Pose 的快速运动目标 6D 位姿估计。这个题目不是单纯做目标检测，而是希望在目标快速运动、图像可能模糊、关键点可能抖动的情况下，仍然从相机图像中稳定输出目标相对于相机的三维位置和姿态。整个系统可以分成三步：第一步用 YOLOv8-Pose 检测小车的二维关键点，第二步用 PnP 把二维关键点和三维模型点对应起来并求解 R 和 t，第三步用 Kalman Filter 结合历史状态，让连续帧输出更加稳定。"
    if slide_index == 2:
        return "这一页是今天的讲解路线。我的讲解会按照从问题到系统的顺序展开：首先说明为什么普通检测框不够，因为检测框只能告诉我们目标在图像中的二维区域；然后说明 YOLOv8-Pose 在系统中负责二维关键点检测；接着说明二维关键点如何通过 PnP 和相机投影几何变成 6D 位姿；之后分析快速运动为什么会带来模糊、遮挡、关键点抖动和位姿抖动；最后说明 Kalman Filter 如何利用上一帧的运动信息提升连续性，并把这些部分落到完整 pipeline 中。"
    if text.startswith("这一页的核心是"):
        return text.replace(
            "这一页的核心是",
            "这一页我主要讲",
            1,
        )
    return text


def to_direct_principle(text: str) -> str:
    text = text.strip()
    text = text.replace("必须", "本页必须")
    text = text.replace("你", "我")
    if not text.startswith("本页"):
        text = "本页重点是：" + text
    return text


def to_direct_backup(text: str) -> str:
    text = text.strip()
    text = text.replace("如果时间紧，", "")
    text = text.replace("如果老师追问，", "问答时我准备补充：")
    text = text.replace("可以准备", "我准备")
    text = text.replace("可以不主动讲", "我不主动展开")
    text = text.replace("可以不", "我不")
    text = text.replace("你", "我")
    if not text.startswith("问答时"):
        text = "问答时我准备补充：" + text
    return text


if __name__ == "__main__":
    main()
