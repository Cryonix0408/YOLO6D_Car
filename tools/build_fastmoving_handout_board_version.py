from __future__ import annotations

import html
import shutil
import zipfile
from pathlib import Path

from build_fastmoving_handout import (
    Slide,
    build_section_lookup,
    content_types_xml,
    copy_slide_images,
    document_rels_xml,
    document_xml,
    heading,
    image_paragraph,
    label,
    numbering_xml,
    p,
    package_rels_xml,
    page_break,
    read_docx_sections,
    read_pptx_slides,
    run,
    settings_xml,
    styles_xml,
    write_docx,
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    work_dir = root / "outputs" / "lecture_handout_work"
    pptx_path = Path(r"C:\Users\25701\Desktop\YOLOv8Pose_FastMoving_1hour_Beautified.pptx")
    docx_path = Path(r"C:\Users\25701\Desktop\YOLO6D_FastMoving_详细公式版_扩展完整版讲义.docx")
    slides_dir = work_dir / "slides"
    output_path = work_dir / "YOLO6D_FastMoving_1hour_长文讲稿_板书公式版.docx"

    slides = read_pptx_slides(pptx_path, slides_dir)
    sections = read_docx_sections(docx_path)
    section_lookup = build_section_lookup(sections)
    copied_images = copy_slide_images(slides, work_dir / "docx_images_board")
    files = build_docx_files(slides, section_lookup, copied_images)
    write_docx(output_path, files)
    print(output_path)


def build_docx_files(
    slides: list[Slide],
    section_lookup: dict[int, list[str]],
    copied_images: dict[int, Path],
) -> dict[str, bytes]:
    media_files: dict[str, bytes] = {}
    image_rels: list[tuple[str, str]] = []
    body: list[str] = []

    body.append(p("YOLO6D Fast-Moving 1小时长文讲稿与板书公式版", style="Title"))
    body.append(p("这一版按演讲现场使用来写：每页先看 PPT 缩略图，再给出可以直接讲的大段话，随后列出黑板/白板上可以直接写的公式和讲解顺序。", style="Subtitle"))
    body.append(callout_box("使用建议", "正式讲的时候，不需要把每一句都念完。你可以先读“现场长文讲稿”形成自己的语言，再把“板书公式”抄到草稿纸上练两遍。被老师追问时，再看“原讲义扩展材料”。"))
    body.append(heading("一小时节奏建议", 1))
    body.append(long_p("这套 38 页 PPT 如果逐页展开会超过一小时，所以现场节奏要有主次。第 1 到 6 页负责把问题讲清楚，大约 8 分钟；第 7 到 13 页讲 YOLOv8-Pose 的角色，大约 12 分钟；第 14 到 24 页是 PnP 与坐标系，是最容易被追问的核心部分，大约 22 分钟；第 25 到 34 页讲 fast-moving 的误差来源和 Kalman，大约 14 分钟；最后 35 到 38 页用 4 分钟收束到系统 pipeline 和总结。"))
    body.append(long_p("这份讲义里的“重点必讲”是你上台一定要说出口的原理；“备讲可跳过”是你要准备但不一定主动展开的内容。数学公式全部尽量写成一行或几行黑板公式，不追求排版华丽，而追求你能现场写、现场解释。"))

    for slide in slides:
        rel_id = f"rId{slide.index}"
        image_name = f"image{slide.index:03d}.png"
        media_files[f"word/media/{image_name}"] = copied_images[slide.index].read_bytes()
        image_rels.append((rel_id, f"media/{image_name}"))

        body.append(page_break())
        body.append(heading(f"第 {slide.index:02d} 页：{slide.title}", 1))
        if slide.subtitle:
            body.append(p(slide.subtitle, style="SlideSubtitle"))
        body.append(image_paragraph(rel_id, image_name, width_in=5.9))

        plan = verbose_plan(slide)
        body.append(label("建议用时", plan["time"]))
        body.append(heading("现场长文讲稿", 2))
        for paragraph in plan["script"]:
            body.append(long_p(paragraph))

        body.append(heading("重点必讲原理", 2))
        for paragraph in plan["must"]:
            body.append(callout_box("重点必讲", paragraph))

        formulas = board_formulas(slide.index)
        body.append(heading("板书公式 / 板书顺序", 2))
        if formulas:
            for formula in formulas:
                body.append(formula_p(formula))
            body.append(long_p(formula_explanation(slide.index)))
        else:
            body.append(long_p("这一页不建议写复杂公式。板书只写关键词即可，例如本页标题、pipeline 三段结构，或者一个箭头链路。这样可以把时间留给后面的 PnP、坐标系和 Kalman。"))

        body.append(heading("备讲可跳过，但需要准备", 2))
        for paragraph in plan["backup"]:
            body.append(long_p(paragraph, style="SourceBody"))

        body.append(heading("原 Word 讲义扩展材料", 2))
        source_chunks = section_lookup.get(slide.index, [])
        if source_chunks:
            for chunk in source_chunks[:20]:
                if chunk.startswith("【"):
                    body.append(p(chunk, style="SourceHeading"))
                else:
                    body.append(long_p(chunk, style="SourceBody"))
        else:
            body.append(long_p("这一页更偏 PPT 过渡或总结，原 Word 讲义中没有完全对应的小节。准备时重点看上面的讲稿和板书提示即可。", style="SourceBody"))

    files: dict[str, bytes] = {}
    files["[Content_Types].xml"] = content_types_xml(len(media_files)).encode("utf-8")
    files["_rels/.rels"] = package_rels_xml().encode("utf-8")
    files["word/_rels/document.xml.rels"] = document_rels_xml(image_rels).encode("utf-8")
    files["word/styles.xml"] = styles_xml().encode("utf-8")
    files["word/numbering.xml"] = numbering_xml().encode("utf-8")
    files["word/settings.xml"] = settings_xml().encode("utf-8")
    files["word/document.xml"] = document_xml("\n".join(body)).encode("utf-8")
    files.update(media_files)
    return files


def verbose_plan(slide: Slide) -> dict[str, object]:
    i = slide.index
    generic = {
        "time": "1.5 min",
        "script": [
            f"这一页的核心是“{slide.title}”。讲的时候先不要急着进入细节，而是先把它放回整条主线：我们从相机图像出发，先通过 YOLOv8-Pose 得到二维关键点，再通过 PnP 把二维关键点和三维模型点联系起来，最后再通过 Kalman 或其他时序方法让输出在快速运动场景下更加连续。",
            "如果听众只记住一句话，就让他们记住：这一页不是孤立知识点，而是整个 YOLO6D 系统中的一个环节。你讲的时候可以先解释它解决什么问题，再解释它的输入输出，最后说明如果这一环出错，会怎样影响后面的位姿结果。",
        ],
        "must": [
            "必须把本页和“2D关键点检测、3D几何求解、时间序列稳定”三件事联系起来讲，不能只停留在概念定义。",
        ],
        "backup": [
            "如果时间紧，这页只讲输入、输出和它在 pipeline 中的位置；如果老师追问，再展开内部细节或公式。",
        ],
    }
    plans: dict[int, dict[str, object]] = {
        1: {
            "time": "1 min",
            "script": [
                "开场时要先把题目讲成一个完整问题，而不是直接说我用了 YOLO。我的目标不是做一个普通检测器，而是在快速运动条件下，让系统能够从相机图像中持续估计小车相对于相机的三维位置和朝向。这里的关键词有三个：YOLOv8-Pose、PnP 和 Kalman。YOLOv8-Pose 负责从图像里找结构点，PnP 负责把结构点变成 6D 位姿，Kalman 负责让连续帧结果更平滑、更稳定。",
                "这一页可以直接告诉听众：后面一小时会围绕一个问题展开，为什么检测框不够，为什么关键点可以接几何，为什么快速运动会让结果抖，以及为什么需要时序滤波。这样老师听完开场就知道你的项目不是简单调用模型，而是把视觉前端、几何后端和动态滤波串成一个系统。",
            ],
            "must": ["必须说清楚三段式结构：Keypoint Detection -> PnP Geometry -> Kalman Temporal Stability。"],
            "backup": ["不要在封面页展开硬件和采集细节，后面系统页再讲。"],
        },
        2: {
            "time": "2 min",
            "script": [
                "这一页是整场汇报的地图。你可以说：我会先从为什么检测框不够开始，因为无人机或机器人真正需要的是目标在三维空间里的位置和朝向；然后讲 YOLOv8-Pose 在这个系统里到底负责什么，它只是输出二维关键点，而不是直接输出 6D 位姿；接着进入 PnP，说明二维关键点如何通过相机内参和三维模型点变成 R 和 t；再讲快速运动为什么会带来模糊、遮挡、关键点抖动；最后讲 Kalman 怎么利用上一帧的信息提升连续性。",
                "这里不需要逐条念目录，而是把目录讲成一条逻辑链。你的语气可以是：这不是六个孤立章节，而是从图像到稳定位姿输出的完整链路。后面每个公式、每个坐标系，都是为了让这个链路能解释清楚、跑得稳定。",
            ],
            "must": ["必须把目录讲成因果链：问题定义 -> 网络输出 -> 几何求解 -> 动态误差 -> 时序滤波 -> 系统评估。"],
            "backup": ["如果时间紧，目录页最多 1 分钟；如果老师比较关注整体结构，可以用 2 分钟把这条主线讲慢一点。"],
        },
        4: {
            "time": "2 min",
            "script": [
                "这一页要把 detection、tracking 和 pose estimation 三个词彻底分开。Detection 只回答当前这一帧有没有目标、目标在哪里、是什么类别，所以它的典型输出是二维框、类别和置信度。Tracking 关心的是连续帧中是不是同一个目标，轨迹有没有断、有没有 ID switch。Pose estimation 更进一步，它关心目标在三维空间中的位置和朝向，也就是相对于相机的 6D pose。",
                "你可以用一句非常直观的话讲：检测框告诉我们小车在图像里的矩形区域，但它不告诉我们车头朝哪、离相机多远、绕哪个方向旋转。我的项目需要的是后者，因为无人机视角下，目标的空间关系比单纯的二维框更重要。这样后面讲关键点和 PnP 时，听众就不会误以为你只是把检测换成了另一个检测模型。",
            ],
            "must": ["必须讲清楚：Detection 是二维定位，Tracking 是时间连续性，Pose 是三维位置和朝向。"],
            "backup": ["ID switch、轨迹关联算法可以不主动讲，除非老师追问 tracking 和 pose tracking 的区别。"],
        },
        5: {
            "time": "1.5 min",
            "script": [
                "这一页要强调信息量的差别。2D box 是图像平面上的矩形，它的坐标只存在于像素平面里；6D pose 是目标坐标系和相机坐标系之间的空间变换。对无人机来说，知道一个目标被框住还不够，因为控制和规划需要知道目标距离、方向、姿态变化趋势。也就是说，box 更像是视觉前端的入口，而 pose 才更接近空间理解。",
                "你可以把这页讲成一个动机：如果我们只做检测，系统只能说“那里有一辆小车”；如果我们做 6D pose，系统可以说“小车在相机前方大约多远，车头朝向哪里，下一步可能怎么运动”。这就是为什么这个项目需要从 YOLOv8-Pose 继续接 PnP，而不能停在检测框。",
            ],
            "must": ["必须说出 2D box 和 6D pose 的本质区别：前者是图像区域，后者是坐标系之间的刚体变换。"],
            "backup": ["如果老师问应用价值，可以联系无人机避障、目标跟随、相对导航。"],
        },
        10: {
            "time": "2 min",
            "script": [
                "这一页要避免一个常见误解：YOLOv8-Pose 不是最终的 6D pose solver。它的任务是在图像中检测目标，并预测一组二维关键点，每个关键点通常包含 u、v 和 confidence。Backbone 负责提取视觉特征，Neck 负责多尺度融合，Pose Head 负责输出 box 和 keypoints。到这里为止，所有结果仍然都在二维图像平面上。",
                "讲的时候可以这样说：我把 YOLOv8-Pose 看作一个可训练的关键点检测前端。它的好处是可以学习小车外观和结构点的位置，但它不知道真实三维尺寸，也不知道相机投影几何。因此我们必须把它输出的二维点送入 PnP，利用已经定义好的三维模型点和相机内参，才能恢复 R 和 t。",
            ],
            "must": ["必须强调 YOLOv8-Pose 的输出是 2D keypoints，不是最终 6D pose。"],
            "backup": ["Backbone、Neck、Head 的细节只讲直觉即可，不需要展开每个网络模块。"],
        },
        12: {
            "time": "2 min",
            "script": [
                "这一页是项目定制部分。YOLOv8-Pose 原本常用于人体关键点，但 pose head 并不要求关键点一定是人体关节。我们可以把小车上稳定、可重复识别、和三维模型有固定对应关系的结构点定义成关键点。例如车头、车尾、车身角点、轮子附近的明显结构点，或者为了 PnP 稳定而定义的虚拟外轮廓点。",
                "这里最重要的是“固定身份”。第一个点永远代表同一个物理位置，第二个点也永远代表同一个物理位置。只要关键点顺序错了，或者某个点的语义在训练集中前后不一致，PnP 就会把错误的 2D-3D 对应关系当作输入，最终求出错误姿态。这也是为什么你之前一直在调整小车角点和外轮廓：关键点定义本身就是 6D pose 系统的基础。",
            ],
            "must": ["必须讲清楚每个关键点都要和一个固定 3D 模型点一一对应。"],
            "backup": ["可以准备解释为什么选择外轮廓点、轮子点、虚拟点，以及它们对 PnP 稳定性的影响。"],
        },
        17: {
            "time": "3 min",
            "script": [
                "这是整场最重要的公式页之一，要慢一点讲。相机投影公式表达的是：物体坐标系中的三维点，先通过 R 和 t 变换到相机坐标系，再通过相机内参 K 投影到图像平面，最后得到像素坐标 u 和 v。这里的 s 是尺度因子，因为透视投影会从三维齐次坐标变成二维齐次坐标。",
                "你可以先从正向过程讲：如果我知道小车的位姿 R、t，也知道某个模型点 P_i 在车体坐标系里的三维坐标，那么我可以算出它应该出现在图像的哪个像素位置。然后反过来，PnP 做的事情就是：我现在已经从 YOLOv8-Pose 得到了很多像素点，同时我也知道它们对应的三维模型点，那么能不能反推出最合理的 R 和 t？这就是 Perspective-n-Point 的意义。",
                "讲这页时一定要把 K、R、t 的角色讲清楚。K 描述相机自身，包括焦距和主点；R、t 描述物体相对于相机的空间关系；三维点来自小车模型；二维点来自 YOLOv8-Pose 预测。四者合起来，才构成从学习模型到几何求解的桥。",
            ],
            "must": ["必须把投影公式讲成“正向投影”和“PnP 反问题”两层含义。"],
            "backup": ["如果老师追问，可以解释齐次坐标、尺度因子 s、以及为什么需要相机标定得到 K。"],
        },
        19: {
            "time": "2.5 min",
            "script": [
                "这一页回答 PnP 为什么能求解。核心思想不是凭空猜一个姿态，而是在所有可能的 R 和 t 中，寻找一个能让三维模型点投影后最接近二维预测关键点的位姿。这里的误差叫重投影误差，也就是预测像素点 p_i 和由当前 R、t 投影出来的像素点之间的距离。",
                "你可以把它讲成一个拟合问题：假设我摆出一个姿态，把小车模型点投影到图像上，如果这些投影点和 YOLO 预测的关键点对得很齐，说明这个姿态很可信；如果投影点偏得很远，说明这个姿态解释不了当前图像。OpenCV 的 solvePnP 本质上就是在这个几何约束下找一个合理解。",
                "这页还可以自然引出 fast-moving 的问题：如果关键点因为模糊或遮挡抖动了几像素，重投影误差的最优解就会变化，R 和 t 也会在连续帧之间跳动。所以后面才需要动态稳定和 Kalman。",
            ],
            "must": ["必须讲清楚重投影误差是连接 2D keypoint 误差和 6D pose 误差的核心指标。"],
            "backup": ["solvePnP 的 EPNP、ITERATIVE、RANSAC 可以备讲，但不建议主动展开。"],
        },
        21: {
            "time": "2 min",
            "script": [
                "坐标系是最容易被追问的部分，所以这页要先把符号说清楚。W 是动捕世界坐标系，动捕系统给出的刚体位姿都在 W 下；C 是相机光学坐标系，也是 PnP 输出位姿所在的坐标系；B_c 是贴在相机上的动捕刚体坐标系；B_o 是贴在小车上的动捕刚体坐标系；O 是我们定义的小车模型坐标系。",
                "这里要强调一个原则：不同系统给出的位姿不一定在同一个坐标系里。动捕给的是世界坐标下的刚体位姿，图像和 PnP 需要的是相机坐标下的物体位姿。如果不做坐标转换，就会出现你之前看到的标签框飞出去、中心偏移、yaw 对不上的问题。那些现象不是网络问题，而是坐标系和外参链路没对齐。",
            ],
            "must": ["必须逐一定义 W、C、B_c、B_o、O，并说明 PnP 最终要的是 T_C^O。"],
            "backup": ["可以准备解释相机刚体质心、标定板刚体、物体刚体重建为什么会影响外参。"],
        },
        23: {
            "time": "3 min",
            "script": [
                "这一页是动捕真值转到相机坐标下的关键公式。动捕直接给的是小车刚体在世界坐标系下的位姿 T_W^B_o，但训练标签和评估通常需要知道小车模型坐标系 O 相对于相机 C 的位姿 T_C^O。因此我们需要把几个固定或实时变换串起来：世界到相机、小车刚体到小车模型、以及动捕给出的世界到小车刚体。",
                "你可以按顺序讲：先从模型点 P^O 出发，通过 T_{B_o}^O 或它的等价定义把模型点放到小车动捕刚体坐标系；再通过 T_W^{B_o} 放到动捕世界坐标；最后通过 T_C^W 转到相机坐标。合起来就是 T_C^O = T_C^W · T_W^{B_o} · T_{B_o}^O。这里每个矩阵的上下标都表示“从哪里到哪里”，顺序不能写反。",
                "这页建议在黑板上一步一步写，不要只把最终公式扔出来。老师如果追问你之前标签为什么偏，很多时候就是这个链路中的某个固定外参、刚体质心、时间同步或矩阵方向出了问题。",
            ],
            "must": ["必须讲清楚链式变换的顺序，以及为什么最后得到的 T_C^O 才能和图像对齐。"],
            "backup": ["准备解释 T_C^W 如何由相机动捕刚体和相机刚体到光学坐标外参得到。"],
        },
        26: {
            "time": "2 min",
            "script": [
                "进入 fast-moving 以后，第一件要讲的是运动模糊。运动模糊的原因很直接：曝光不是瞬间完成的，而是在一段时间内积分光线。如果目标在曝光时间内移动了，它在图像上就不是一个清晰位置，而是一段拖影。对人眼来说可能只是有点糊，对网络来说则意味着边缘、角点、纹理这些浅层特征被破坏。",
                "这会产生连锁反应。Backbone 提取到的特征质量下降，Pose Head 对关键点位置的回归会不稳定，关键点一抖，PnP 解出的 R 和 t 也会抖。也就是说 fast-moving 的难点不是单一模块的问题，而是从图像采集层开始一路传递到几何后端和时序输出。",
            ],
            "must": ["必须把运动模糊讲成“曝光期间位移造成的特征破坏”，再连接到 keypoint jitter。"],
            "backup": ["可以准备讲全局快门、曝光时间、补光和增益的取舍：短曝光能减小模糊，但会变暗；高增益能变亮，但会增噪。"],
        },
        28: {
            "time": "2.5 min",
            "script": [
                "这一页要解释为什么看起来很小的关键点误差会导致明显的位姿抖动。PnP 不是独立看某一个点，而是利用所有 2D-3D 对应点之间的整体几何结构。如果一个点偏了几像素，多个点又各自随机偏，最优的 R 和 t 就会跟着变化。有时二维图像上的偏差看起来不大，但转成三维位姿后，yaw、depth 或 translation 可能会出现明显跳动。",
                "你可以把它讲成误差传播链：二维关键点误差 Δp 经过 PnP 的几何求解，变成位姿扰动 ΔR 和 Δt。这个传播和点的空间分布、相机距离、目标大小、可见点数量都有关系。目标越远、像素占比越小、点越集中，几像素误差造成的三维位姿影响就越明显。",
            ],
            "must": ["必须讲出 Δp -> ΔR, Δt 的误差传播关系，这是后面 Kalman 的动机。"],
            "backup": ["可以准备雅可比形式的误差传播，但现场不需要推导。"],
        },
        29: {
            "time": "2 min",
            "script": [
                "这一页是评价指标的防守页。很多人会问：既然训练 mAP 很高，为什么实际 demo 还可能抖？答案是 mAP 主要评价检测或关键点在单帧上的平均精度，它不直接评价 PnP 解出来的旋转误差、平移误差，也不直接评价连续帧之间的位姿抖动和轨迹连续性。",
                "因此 fast-moving 项目不能只看 mAP。你可以说：mAP 高说明前端检测基本可用，但系统最终要看的是 translation error、rotation error、reprojection error、jitter、latency 和 FPS。尤其在快速运动下，单帧准确和连续稳定是两个不同目标。Kalman 要解决的就是后者的一部分。",
            ],
            "must": ["必须说清楚：mAP 高不等于 6D pose 稳，更不等于 tracking 连续。"],
            "backup": ["准备几个评估指标名称：ADD、rotation error、translation error、reprojection error、pose jitter、latency。"],
        },
        33: {
            "time": "3 min",
            "script": [
                "Kalman 公式页不建议完整推导，而是解释每一项代表什么。预测步用上一时刻状态和运动模型预测当前状态，更新步把当前观测和预测值融合。状态 x 可以包含位置、速度，也可以扩展到姿态参数；F 是运动模型，例如匀速模型；z 是当前帧由 YOLOv8-Pose + PnP 得到的观测；H 把状态映射到观测空间；K 是 Kalman gain，它决定更相信模型预测还是更相信当前观测。",
                "讲的时候要强调 Kalman 不是简单平均。简单平均只会平滑，但不理解运动趋势；Kalman 同时维护状态和不确定性。如果当前观测噪声大，滤波器会更相信预测；如果预测不确定性大，而观测比较可靠，它会更相信观测。这个机制正好适合 fast-moving 场景，因为某些帧会因为模糊或遮挡变得不可靠。",
            ],
            "must": ["必须讲清楚 Prediction、Measurement、Update，以及 Kalman gain 的直觉。"],
            "backup": ["如果老师追问，可以展开 Q 和 R：Q 表示过程噪声，R 表示观测噪声，它们控制滤波器对运动模型和观测的信任程度。"],
        },
        37: {
            "time": "2 min",
            "script": [
                "这一页把前面的内容收束到在线 pipeline。相机每来一帧 RGB 图像，YOLOv8-Pose 先输出二维关键点；然后系统筛掉低置信度或不可用点，把剩下的 2D-3D 对应送入 PnP；PnP 得到单帧的 R 和 t；最后 Kalman 把当前观测和历史运动状态融合，输出更稳定的 6D pose。",
                "这里要强调实时性。对于 fast-moving demo，不能只看最后姿态对不对，还要看延迟、帧率和稳定性。如果处理太慢，即使单帧精度高，也无法用于快速运动目标。你可以把这页作为工程落点：前面讲的网络、几何、滤波，最后都要在这个 pipeline 里实时跑起来。",
            ],
            "must": ["必须把在线链路讲完整：RGB -> YOLOv8-Pose -> PnP -> Kalman -> Stable 6D Pose。"],
            "backup": ["可以准备讲海康工业相机、短曝光、全局快门、连续帧采集和后续同步评估。"],
        },
        38: {
            "time": "2 min",
            "script": [
                "总结页不要再引入新知识，只收束三句话。第一，YOLOv8-Pose 在这个项目里解决的是二维关键点检测，不是直接输出 6D 位姿。第二，二维关键点、三维模型点和相机内参通过 PnP 联系起来，才能求出 R 和 t。第三，快速运动真正难的是时序稳定性，因为模糊、遮挡和视角变化会让关键点和 PnP 结果抖动，所以需要 Kalman 和动态评价指标。",
                "最后可以抛出一个问题作为结束：如果检测框很准，为什么位姿仍然可能不稳定？这个问题能把整场内容串起来。因为检测框只说明目标区域对，关键点可能仍然抖；关键点抖会传到 PnP；PnP 单帧结果抖会影响 tracking；所以 fast-moving 的核心不是单点精度，而是完整链路的稳定输出。",
            ],
            "must": ["必须用三句话总结 YOLOv8-Pose、PnP、Kalman 的分工。"],
            "backup": ["如果有问答，就优先回到“关键点误差传播”和“坐标系转换”两个最核心问题。"],
        },
    }
    return plans.get(i, generic)


def board_formulas(index: int) -> list[str]:
    formulas: dict[int, list[str]] = {
        4: ["Detection: I_t -> {bbox_t, class_t, score_t}", "Tracking: {I_1,...,I_T} -> {state_1,...,state_T}", "Pose: T_C^O = [ R_C^O  t_C^O ; 0  1 ]"],
        5: ["2D box = (x_c, y_c, w, h)", "6D pose = (x, y, z, roll, pitch, yaw)", "or: T = [R t; 0 1] in SE(3)"],
        8: ["Image: I in R^(H x W x 3)", "pixel: I(u, v) = [R, G, B]"],
        9: ["Y(i,j,k) = sum_c sum_m sum_n X(i+m,j+n,c) * W(m,n,c,k) + b_k", "shallow features -> edges / texture", "deep features -> parts / semantics"],
        10: ["YOLOv8-Pose(I) -> bbox + { (u_i, v_i, conf_i) }_{i=1..N}", "Important: output is 2D keypoints, not 6D pose"],
        12: ["3D model point: P_i^O = (X_i, Y_i, Z_i)", "2D keypoint: p_i = (u_i, v_i)", "fixed identity: P_i^O <-> p_i"],
        13: ["label = class xc yc w h x1 y1 v1 ... xN yN vN", "x,y are normalized image coordinates", "v means keypoint visibility / availability"],
        15: ["Known: P_i^O = (X_i, Y_i, Z_i)", "Measured: p_i = (u_i, v_i)", "Need: correspondence P_i^O <-> p_i"],
        16: ["solvePnP( {P_i^O}, {p_i}, K ) -> R_C^O, t_C^O", "Output pose: T_C^O = [R_C^O t_C^O; 0 1]"],
        17: ["s * [u, v, 1]^T = K [R | t] [X, Y, Z, 1]^T", "P_C = R * P_O + t", "p = project( K * P_C )"],
        18: ["K = [ fx  0  cx ; 0  fy  cy ; 0  0  1 ]", "fx, fy: focal length in pixels", "cx, cy: principal point"],
        19: ["min_{R,t} sum_i || p_i - project( K (R P_i + t) ) ||^2", "reprojection error e_i = ||p_i - p_i_hat||"],
        21: ["W: mocap world", "C: camera optical frame", "B_c: camera rigid body", "B_o: object rigid body", "O: object model frame"],
        22: ["T_A^B = [ R_A^B  t_A^B ; 0  1 ]", "point transform: P_A = T_A^B * P_B", "composition: T_A^C = T_A^B * T_B^C"],
        23: ["T_C^O = T_C^W * T_W^(B_o) * T_(B_o)^O", "model point to camera: P_C = T_C^O * P_O"],
        24: ["T_W^C = T_W^(B_c) * T_(B_c)^C", "T_C^W = inverse( T_W^C )", "then: T_C^O = T_C^W * T_W^(B_o) * T_(B_o)^O"],
        26: ["blur_length_px ≈ image_velocity_px_per_s * exposure_time_s", "short exposure -> less blur, but darker image", "higher gain -> brighter image, but more noise"],
        28: ["keypoint noise: p_i -> p_i + delta_p_i", "pose perturbation: delta_xi ≈ (J^T J)^(-1) J^T delta_p", "so: Delta p -> Delta R, Delta t"],
        29: ["mAP high != keypoints stable", "keypoints stable != PnP pose stable", "pose stable != tracking continuous"],
        30: ["Fast motion -> blur/viewpoint/occlusion -> feature noise -> keypoint jitter -> pose jitter", "This is an error propagation chain."],
        32: ["Prediction: use previous state to guess current state", "Measurement: z_k = pose from YOLOv8-Pose + PnP", "Update: combine prediction and measurement"],
        33: ["Prediction: x_hat_k^- = F x_hat_(k-1) + B u_k", "Covariance: P_k^- = F P_(k-1) F^T + Q", "Update: x_hat_k = x_hat_k^- + K_k (z_k - H x_hat_k^-)", "K_k = P_k^- H^T (H P_k^- H^T + R)^(-1)"],
        34: ["Option A: filter 2D keypoints p_i = (u_i, v_i)", "Option B: filter 6D pose x = [t, rotation, velocity]", "baseline: PnP first, then Kalman on pose"],
        36: ["mocap GT: T_W^(B_o)", "label projection: p_i = project( K * T_C^O * P_i^O )", "T_C^O = T_C^W * T_W^(B_o) * T_(B_o)^O"],
        37: ["Online: I_t -> YOLO -> keypoints p_t", "PnP: (p_t, P^O, K) -> T_C^O(t)", "Kalman: T_raw(t) -> T_smooth(t)"],
        38: ["YOLOv8-Pose: image -> 2D keypoints", "PnP: 2D-3D correspondences -> R,t", "Kalman: raw pose sequence -> stable pose sequence"],
    }
    return formulas.get(index, [])


def formula_explanation(index: int) -> str:
    explanations = {
        17: "这组公式板书时先写中间式 P_C = R P_O + t，再写完整投影公式。这样听众能先理解三维点如何到相机坐标，再理解相机内参 K 如何把它投到像素平面。",
        19: "这页公式要强调“最小化”的含义：PnP 找的不是任意姿态，而是让投影点最贴近 YOLO 预测点的姿态。重投影误差也是后续判断标签质量和位姿可信度的重要指标。",
        23: "板书时务必从右往左解释矩阵作用顺序：模型点先在 O 中，再到小车刚体，再到世界，最后到相机。这样可以避免把 T 的方向讲反。",
        33: "Kalman 的公式不需要推导矩阵维度，但要讲清楚 K_k 的直觉：它像一个动态权重，决定当前帧更相信预测还是更相信观测。",
    }
    return explanations.get(index, "板书时先写变量定义，再写主公式，最后用一句话解释这个公式在系统中的作用。不要追求推导完整，重点是让老师看到你知道每个符号代表什么。")


def long_p(text: str, style: str = "Normal") -> str:
    return p(text, style=style)


def callout_box(label_text: str, text: str) -> str:
    return f'<w:p><w:pPr><w:pStyle w:val="CalloutMust"/></w:pPr>{run(label_text + "：", bold=True)}{run(text)}</w:p>'


def formula_p(text: str) -> str:
    escaped = html.escape(text)
    return f"""
<w:p>
  <w:pPr>
    <w:spacing w:before="60" w:after="60"/>
    <w:shd w:fill="F8FAFC"/>
    <w:pBdr>
      <w:top w:val="single" w:sz="12" w:space="3" w:color="DC2626"/>
      <w:left w:val="single" w:sz="12" w:space="3" w:color="DC2626"/>
      <w:bottom w:val="single" w:sz="12" w:space="3" w:color="DC2626"/>
      <w:right w:val="single" w:sz="12" w:space="3" w:color="DC2626"/>
    </w:pBdr>
  </w:pPr>
  <w:r>
    <w:rPr>
      <w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="Microsoft YaHei"/>
      <w:sz w:val="21"/>
      <w:color w:val="0F172A"/>
    </w:rPr>
    <w:t xml:space="preserve">{escaped}</w:t>
  </w:r>
</w:p>"""


if __name__ == "__main__":
    main()
