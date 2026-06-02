from __future__ import annotations

import html
from pathlib import Path

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


OUTPUT_NAME = "YOLO6D_FastMoving_1hour_逐字讲稿_修正版_红框板书.docx"


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    work_dir = root / "outputs" / "lecture_handout_work"
    pptx_path = Path(r"C:\Users\25701\Desktop\YOLOv8Pose_FastMoving_1hour_Beautified.pptx")
    slides_dir = work_dir / "slides"
    output_path = work_dir / OUTPUT_NAME

    slides = read_pptx_slides(pptx_path, slides_dir)
    copied_images = copy_slide_images(slides, work_dir / "docx_images_clean_script")

    files = build_docx_files(slides, copied_images)
    write_docx(output_path, files)
    print(output_path)


def build_docx_files(slides: list[Slide], copied_images: dict[int, Path]) -> dict[str, bytes]:
    media_files: dict[str, bytes] = {}
    image_rels: list[tuple[str, str]] = []
    body: list[str] = []

    body.append(p("YOLO6D Fast-Moving 1小时逐字讲稿修正版", style="Title"))
    body.append(
        p(
            "这版只保留可直接读出口的讲稿、红框板书公式和问答备稿。红色边框里的内容就是建议现场写到黑板或白板上的内容。",
            style="Subtitle",
        )
    )
    body.append(heading("整体叙事判断", 1))
    body.append(
        clean_p(
            "这套 PPT 的主线总体是清晰的：先解释为什么二维检测框不够，再说明 YOLOv8-Pose 只负责二维关键点，接着用 PnP 把二维关键点和三维模型点连接起来，然后解决坐标系和动捕真值对齐，最后进入快速运动下的抖动问题和 Kalman 时序稳定。这个顺序符合听众理解路径。"
        )
    )
    body.append(
        clean_p(
            "需要注意的是，第 3 到 6 页都在讲动机，现场不要每页都重复“检测框不够”。第 8 到 9 页的 CNN 基础偏铺垫，如果时间紧可以快讲。第 21 到 24 页是最容易被老师追问的核心，应当慢讲。第 31 到 34 页 Kalman 部分不用完整推导，但要把 prediction、measurement、update 和 Kalman gain 的直觉讲清楚。"
        )
    )
    body.append(heading("一小时节奏", 1))
    for item in [
        "0-8 min：问题定义，说明为什么从 2D box 走向 6D pose。",
        "8-20 min：YOLOv8-Pose 前端，说明网络输出的是二维关键点。",
        "20-36 min：PnP 和相机投影，讲清 2D-3D 对应、内参 K、重投影误差。",
        "36-46 min：坐标系和动捕真值转换，重点讲 T 的方向和链式变换。",
        "46-56 min：快速运动误差和 Kalman，解释为什么要做时序稳定。",
        "56-60 min：系统 pipeline、评估指标和总结。"
    ]:
        body.append(clean_p(item))

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
        body.append(label("建议用时", plan["time"]))

        body.append(heading("逐字讲稿", 2))
        body.append(clean_p(plan["script"]))

        body.append(heading("红框板书", 2))
        formulas = plan.get("board", [])
        if formulas:
            for formula in formulas:
                body.append(board_formula(formula))
        else:
            body.append(clean_p("这一页不写公式，只在口头上完成过渡。"))

        body.append(heading("问答备稿", 2))
        for backup in plan.get("backup", []):
            body.append(clean_p(backup, style="SourceBody"))

    body_xml = "\n".join(body)
    files: dict[str, bytes] = {
        "[Content_Types].xml": content_types_xml(len(media_files)).encode("utf-8"),
        "_rels/.rels": package_rels_xml().encode("utf-8"),
        "word/_rels/document.xml.rels": document_rels_xml(image_rels).encode("utf-8"),
        "word/styles.xml": styles_xml().encode("utf-8"),
        "word/numbering.xml": numbering_xml().encode("utf-8"),
        "word/settings.xml": settings_xml().encode("utf-8"),
        "word/document.xml": document_xml(body_xml).encode("utf-8"),
    }
    files.update(media_files)
    return files


def clean_p(text: str, style: str = "Normal") -> str:
    return p(text, style=style)


def board_formula(text: str) -> str:
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


def fallback_plan(slide: Slide) -> dict[str, object]:
    return {
        "time": "1 min",
        "script": f"这一页我只做过渡。标题是“{slide.title}”，它的作用是把上一部分内容连接到下一部分内容。这里我不展开新公式，只提醒大家后面的内容仍然围绕同一条主线：二维关键点、PnP 几何求解和快速运动下的时序稳定。",
        "board": [],
        "backup": ["如果时间紧，这类过渡页可以压缩到二十秒以内。"],
    }


CLEAN_PLAN: dict[int, dict[str, object]] = {
    1: {
        "time": "1 min",
        "script": "各位老师好，我今天汇报的题目是基于 YOLOv8-Pose 的快速运动目标 6D 位姿估计。我的目标不是只检测图像中有没有小车，而是在小车快速运动、图像可能模糊、关键点可能抖动的情况下，仍然稳定估计小车相对于相机的三维位置和朝向。整套方法可以概括成三段：YOLOv8-Pose 负责输出二维关键点，PnP 负责把二维关键点和三维模型点变成 R 和 t，Kalman Filter 负责让连续帧结果更平滑、更稳定。",
        "board": ["I_t -> YOLOv8-Pose -> 2D keypoints -> PnP -> T_C^O -> Kalman -> stable pose"],
        "backup": ["封面页不展开硬件细节，先把三段式系统框架讲清楚。"],
    },
    2: {
        "time": "2 min",
        "script": "这一页是今天的讲解路线。我会先回答为什么检测框不够，因为二维框只能说明目标在图像中的区域，不能说明距离和朝向。然后我会讲 YOLOv8-Pose 在系统里到底负责什么，它输出的是二维关键点，不是最终 6D 位姿。接着进入 PnP，说明二维关键点、三维模型点和相机内参如何共同求解 R 和 t。最后我会讨论快速运动带来的模糊、遮挡和抖动，并说明 Kalman Filter 如何利用历史状态提升连续性。",
        "board": ["问题定义 -> 2D关键点 -> PnP几何 -> 坐标系对齐 -> 快速运动误差 -> Kalman稳定"],
        "backup": ["目录页不要逐条念 PPT，要讲成因果链。"],
    },
    3: {
        "time": "1 min",
        "script": "这一章先解释动机：为什么检测框不够。普通检测只能告诉我图像里哪个区域有目标，但对于无人机或者移动机器人来说，更重要的是目标在三维空间里的位置、朝向和运动趋势。也就是说，我需要从“看见目标”进一步走向“理解目标和相机之间的空间关系”。后面的关键点、PnP 和 Kalman 都是在为这个目标服务。",
        "board": ["2D box: where in image?     6D pose: where and how in 3D?"],
        "backup": ["这页只建立问题，不重复后面每个模块的细节。"],
    },
    4: {
        "time": "2 min",
        "script": "这里我把 detection、tracking 和 pose estimation 分开讲。Detection 回答的是当前帧有没有目标、目标在哪里；tracking 回答的是连续帧里是不是同一个目标，以及轨迹是否连续；pose estimation 回答的是目标在三维空间中的位置和朝向。我的项目最终关心的是 pose，因为只有 pose 才能描述小车相对于相机的空间关系。",
        "board": ["Detection: I_t -> bbox_t", "Tracking: {bbox_t} -> trajectory / ID", "Pose: T_C^O = [ R_C^O  t_C^O ; 0  1 ]"],
        "backup": ["ID switch 等 tracking 细节可以不主动展开。"],
    },
    5: {
        "time": "1.5 min",
        "script": "这一页强调 2D box 和 6D pose 的信息量差别。二维框只存在于像素平面，它能告诉我小车大概在哪个矩形区域里；6D pose 描述的是目标坐标系和相机坐标系之间的刚体变换，包含三维平移和三维旋转。对于无人机视角，系统不仅要知道小车在画面里，还要知道它离相机多远、车头朝向哪里、下一步可能怎么运动。",
        "board": ["2D box: b = (x_c, y_c, w, h)", "6D pose: (x, y, z, roll, pitch, yaw)", "T = [R t; 0 1]  in SE(3)"],
        "backup": ["如果老师问应用价值，可以联系目标跟随、相对导航和避障。"],
    },
    6: {
        "time": "1 min",
        "script": "这一页把问题落到无人机视觉感知链路。目标检测只是入口，它负责找到小车；关键点检测进一步给出小车结构点的位置；PnP 根据 2D-3D 对应恢复三维位置和朝向；时序平滑则保证连续帧输出不会剧烈跳动。后面的讲解会按照这条链路展开。",
        "board": ["Detection -> Keypoints -> PnP pose -> Temporal smoothing -> Control / decision"],
        "backup": ["这一页与第 3 页都属于动机页，现场要快，不要重复讲。"],
    },
    7: {
        "time": "0.5 min",
        "script": "接下来进入 YOLOv8-Pose 部分。这里我要强调一个定位：YOLOv8-Pose 是关键点检测前端，它负责从图像里找结构点，但它不是最终的 6D 位姿求解器。真正把关键点变成位姿的是后面的 PnP 几何。",
        "board": ["YOLOv8-Pose = 2D keypoint frontend"],
        "backup": ["这页是章节页，可以快速过渡。"],
    },
    8: {
        "time": "1 min",
        "script": "图像进入网络之前，本质上是一个三维数组。H 和 W 是图像高宽，3 表示 RGB 三个通道。网络并不是直接理解“小车”这个概念，而是先从像素矩阵里提取边缘、纹理、局部结构，最后回归出检测框和关键点。因此图像质量会直接影响后续关键点质量。",
        "board": ["I ∈ R^(H x W x 3)", "pixel: I(u,v) = [R, G, B]"],
        "backup": ["如果听众熟悉深度学习，这页可以压缩。"],
    },
    9: {
        "time": "1 min",
        "script": "CNN 特征提取可以用直觉理解：浅层更关注边缘、纹理和颜色变化，中层开始看到局部部件，深层更接近目标整体结构。快速运动会首先破坏这些浅层视觉特征，比如边缘变糊、角点不清晰，随后影响关键点回归。这也是为什么 fast-moving 不只是后端滤波问题，前端图像质量也很关键。",
        "board": ["shallow: edges / texture", "middle: parts", "deep: object structure"],
        "backup": ["卷积公式不是本项目重点，不需要展开推导。"],
    },
    10: {
        "time": "2 min",
        "script": "这一页说明 YOLOv8-Pose 的角色。RGB 图像输入后，backbone 提取特征，neck 做多尺度融合，pose head 输出检测框、关键点坐标和关键点置信度。到这里为止，所有输出仍然在二维图像平面上。它能告诉我第 i 个关键点的像素坐标是 u_i、v_i，以及这个点是否可靠；但它不知道真实三维尺寸，也不会直接输出 R 和 t。",
        "board": ["YOLOv8-Pose(I) -> bbox + {(u_i, v_i, c_i)}_{i=1..N}", "output: 2D keypoints, not 6D pose"],
        "backup": ["Backbone、Neck、Head 只讲功能，不讲网络层细节。"],
    },
    11: {
        "time": "1 min",
        "script": "YOLOv8-Detect 和 YOLOv8-Pose 的区别在于输出。Detect 只输出 box、类别和置信度，适合普通目标检测；Pose 除了 box 以外，还输出一组关键点和关键点置信度。对我的任务来说，关键点是连接图像和三维几何的桥，因此必须使用 pose 版本，而不是只用 detect 版本。",
        "board": ["YOLO Detect: bbox + class + score", "YOLO Pose: bbox + class + keypoints + keypoint scores"],
        "backup": ["如果问为什么不用检测框直接估位姿，回到 2D box 信息不足。"],
    },
    12: {
        "time": "2 min",
        "script": "这里是物体关键点设计。YOLOv8-Pose 原本常用于人体关键点，但关键点并不一定是人体关节，也可以是小车上固定的结构点。最重要的是每个关键点必须有固定身份：第一个点永远对应同一个物理位置，第二个点也永远对应同一个物理位置。只要关键点身份混乱，PnP 的 2D-3D 对应就会错，最终姿态也会错。",
        "board": ["p_i = (u_i, v_i)  <->  P_i^O = (X_i, Y_i, Z_i)", "same index i = same physical point"],
        "backup": ["可补充轮子点、车身角点和虚拟外轮廓点如何提高 PnP 稳定性。"],
    },
    13: {
        "time": "1.5 min",
        "script": "训练标签同时包含检测框和关键点。检测框帮助网络定位目标区域，关键点描述目标结构。每个关键点通常包含归一化后的 x、y，以及 visibility 或 confidence 标记。标签质量直接决定网络能否学会稳定的结构点，因此自动标注时必须保证关键点顺序、可见性和坐标都一致。",
        "board": ["label = class, box, kp_1, ..., kp_N", "kp_i = (x_i, y_i, v_i)"],
        "backup": ["这页不需要讲 YOLO txt 文件每个字段的全部细节。"],
    },
    14: {
        "time": "0.5 min",
        "script": "从这一页开始进入 PnP。前面 YOLOv8-Pose 已经给出了二维关键点，但二维点本身还不是三维位姿。PnP 的作用就是把图像中的二维点和物体模型中的三维点联系起来，求出物体坐标系相对于相机坐标系的旋转和平移。",
        "board": ["2D keypoints + 3D model points + K -> R, t"],
        "backup": ["章节页快速过渡即可。"],
    },
    15: {
        "time": "2 min",
        "script": "同一个物理点有两种表达。它在图像里是像素坐标 p_i，也就是 u_i、v_i；它在小车模型坐标系里是三维坐标 P_i^O，也就是 X_i、Y_i、Z_i。PnP 依赖的是这两者之间的一一对应关系。如果二维第一个点对应的是车头左角，而三维第一个点却写成了车尾点，几何求解一定会错。",
        "board": ["2D: p_i = [u_i, v_i]^T", "3D: P_i^O = [X_i, Y_i, Z_i]^T", "correspondence: p_i <-> P_i^O"],
        "backup": ["这页可以联系前面关键点身份固定。"],
    },
    16: {
        "time": "2 min",
        "script": "PnP 的输入是多组 2D-3D 对应点和相机内参 K，输出是旋转 R 和平移 t。这里的 R 和 t 表示从物体模型坐标系 O 到相机光学坐标系 C 的变换。换句话说，PnP 求的是小车在相机坐标系下的位置和朝向，通常写成 T_C^O。",
        "board": ["Input: {p_i}, {P_i^O}, K", "Output: R_C^O, t_C^O", "T_C^O = [R_C^O  t_C^O; 0 1]"],
        "backup": ["如果被追问，强调上标下标代表从 O 到 C。"],
    },
    17: {
        "time": "3 min",
        "script": "这是核心投影公式。一个三维模型点 P_i^O 先通过 R 和 t 变到相机坐标系，得到 P_i^C；再通过相机内参 K 投影到像素平面，得到 u_i、v_i。这里的 s 是齐次坐标尺度因子。正向看，如果我知道 R 和 t，就能算出模型点应该投影到哪里；反向看，PnP 就是在已知二维投影点和三维模型点的情况下，求最合理的 R 和 t。",
        "board": ["P_i^C = R_C^O P_i^O + t_C^O", "s [u_i, v_i, 1]^T = K P_i^C", "s [u_i, v_i, 1]^T = K [R_C^O | t_C^O] [X_i, Y_i, Z_i, 1]^T"],
        "backup": ["板书时先写 P_i^C，再写完整投影式，别一上来写大公式。"],
    },
    18: {
        "time": "2 min",
        "script": "相机内参 K 描述相机自己的成像方式。f_x 和 f_y 是像素单位下的焦距，c_x 和 c_y 是主点坐标，通常接近图像中心。不同相机、不同镜头、不同分辨率都会改变 K。因此换成海康工业相机或者换镜头以后，内参需要重新标定，否则 PnP 的几何比例会错。",
        "board": ["K = [[f_x, 0, c_x], [0, f_y, c_y], [0, 0, 1]]", "change camera / lens / resolution -> recalibrate K"],
        "backup": ["这页可联系你从 D455 换到海康相机后的标定需求。"],
    },
    19: {
        "time": "2.5 min",
        "script": "PnP 本质上是在最小化重投影误差。给定某个候选 R 和 t，我可以把每个三维模型点投影到图像上，得到预测投影点；然后计算它和 YOLOv8-Pose 输出的关键点之间的距离。所有点的距离平方和越小，说明这组位姿越能解释当前图像观测。快速运动时关键点会抖，重投影误差的最优解也会跟着变，这就是位姿抖动的来源之一。",
        "board": ["e_i = p_i - π(K(RP_i^O + t))", "min_{R,t} Σ_i ||e_i||_2^2"],
        "backup": ["solvePnP 的 EPNP、ITERATIVE、RANSAC 可以作为问答准备，不主动展开。"],
    },
    20: {
        "time": "0.5 min",
        "script": "下面进入坐标系转换。位姿不是一个孤立数字，而是两个坐标系之间的关系。如果坐标系定义不清楚，R、t、四元数和动捕真值都可能被解释错。项目里标签框偏移、yaw 对不上、质心不一致，很多时候都不是网络问题，而是坐标系链路没有对齐。",
        "board": ["Pose = transform between coordinate frames"],
        "backup": ["这是整场最容易被追问的部分，要慢下来。"],
    },
    21: {
        "time": "2 min",
        "script": "项目里至少有五个坐标系。W 是动捕世界坐标系，C 是相机光学坐标系，B_c 是相机上的动捕刚体坐标系，B_o 是小车上的动捕刚体坐标系，O 是我们定义的小车模型坐标系。动捕系统直接给的是世界坐标下的刚体位姿，而 PnP 和图像对齐需要的是相机坐标下的物体位姿，所以必须通过外参把它们统一起来。",
        "board": ["W: mocap world", "C: camera optical", "B_c: camera rigid body", "B_o: object rigid body", "O: object model"],
        "backup": ["先定义坐标系，再写链式变换，顺序不能反。"],
    },
    22: {
        "time": "2 min",
        "script": "齐次变换矩阵把旋转和平移放在同一个矩阵里。T_A^B 表示把 B 坐标系中的点变换到 A 坐标系。这个符号非常重要，因为矩阵乘法是有方向的。组合变换时，右边的变换先作用，左边的变换后作用。如果方向写反，图像里的标签框就会飞出去。",
        "board": ["T_A^B = [ R_A^B  t_A^B ; 0 1 ]", "P^A = T_A^B P^B", "T_A^C = T_A^B T_B^C"],
        "backup": ["上标下标解释清楚，比推导更重要。"],
    },
    23: {
        "time": "3 min",
        "script": "这一页是动捕真值转到相机坐标系下的关键链路。我们最终想要的是小车模型坐标系 O 相对于相机 C 的位姿 T_C^O。动捕给的是小车刚体 B_o 在世界 W 下的位姿 T_W^{B_o}；小车刚体到小车模型之间有一个固定外参 T_{B_o}^O；世界到相机的变换是 T_C^W。因此它们串起来就是 T_C^O。这个公式必须从右往左解释：模型点先到小车刚体，再到世界，最后到相机。",
        "board": ["T_C^O = T_C^W · T_W^{B_o} · T_{B_o}^O", "read right to left: O -> B_o -> W -> C"],
        "backup": ["如果老师问标签为什么偏，就回到外参、时间同步、刚体质心和矩阵方向。"],
    },
    24: {
        "time": "2 min",
        "script": "如果相机也贴了动捕刚体，还需要把相机刚体坐标系转换到相机光学坐标系。动捕能测到 T_W^{B_c}，也就是相机刚体在世界中的位姿；标定得到固定外参 T_{B_c}^C；两者相乘得到相机光学坐标系在世界中的位姿，再取逆得到世界到相机的 T_C^W。换相机、换镜头、移动相机刚体结构后，都需要重新检查这条链路。",
        "board": ["T_W^C = T_W^{B_c} · T_{B_c}^C", "T_C^W = (T_W^C)^(-1)"],
        "backup": ["这里可以联系海康相机换机后的外参重标定。"],
    },
    25: {
        "time": "0.5 min",
        "script": "前面讲完了单帧几何，现在进入快速运动问题。快速运动的难点不是某一个模块坏掉，而是误差会从图像采集层一路传到特征、关键点、PnP 位姿和跟踪输出。接下来几页就是解释这条误差传导链。",
        "board": ["image error -> keypoint error -> pose error -> tracking instability"],
        "backup": ["章节页快速过渡即可。"],
    },
    26: {
        "time": "2 min",
        "script": "运动模糊来自曝光期间目标发生位移。相机不是在一个数学瞬间成像，而是在曝光时间内积分光线。如果小车在这段时间内移动，边缘和角点会被拉成拖影。对 YOLOv8-Pose 来说，这会降低 backbone 提取到的浅层特征质量，进一步让 pose head 输出的关键点变得不稳定。",
        "board": ["blur length ∝ image velocity × exposure time", "short exposure -> less blur, but darker image"],
        "backup": ["短曝光减少模糊，高增益会增噪，补光能改善信噪比。"],
    },
    27: {
        "time": "2 min",
        "script": "除了模糊，快速运动还会带来视角、尺度和遮挡变化。同一辆小车从不同角度看，外观差异很大；距离快速变化时，目标在图像中的尺度也会快速变化；部分车身或轮子被遮挡时，关键点可能不可见。这样连续帧之间的观测就不再平滑，后面的 PnP 和 tracking 都会受到影响。",
        "board": ["viewpoint change + scale change + occlusion -> lower temporal consistency"],
        "backup": ["这页不用公式，重点是把动态难点讲成连续帧问题。"],
    },
    28: {
        "time": "2.5 min",
        "script": "关键点抖动会变成位姿抖动。表面上看，一个二维关键点只偏了几像素，但 PnP 使用的是所有点之间的整体几何关系。多个点的随机偏移会改变最优的 R 和 t。目标越远、像素占比越小、关键点越集中，同样的像素误差对三维位姿的影响就越明显。",
        "board": ["Δp_i -> ΔR, Δt", "pose jitter = frame-to-frame variation of R,t"],
        "backup": ["如果被追问，可以说更严格的分析会用 PnP 雅可比做误差传播。"],
    },
    29: {
        "time": "2 min",
        "script": "这一页解释为什么高 mAP 仍然不够。mAP 主要评价检测框、类别和关键点在单帧上的平均表现，但 fast-moving demo 最终关心的是位姿误差、连续性、延迟和帧率。一个模型 mAP 很高，仍然可能在快速运动时输出抖动的 R 和 t。因此系统评估不能只看训练结果图，还要看 rotation error、translation error、reprojection error、pose jitter 和 latency。",
        "board": ["mAP high ≠ keypoints stable ≠ pose stable", "metrics: e_R, e_t, reproj error, jitter, FPS, latency"],
        "backup": ["这是答辩防守页，要主动讲。"],
    },
    30: {
        "time": "1.5 min",
        "script": "这一页把误差链路收束起来。快速运动导致模糊、视角变化和遮挡；这些问题破坏图像特征；特征不稳定导致关键点抖动；关键点抖动经过 PnP 传导成位姿抖动。也就是说，问题不只在 detector，也不只在 PnP，而是在完整链路里逐级放大。因此后面需要时序滤波和动态评价指标。",
        "board": ["fast motion -> blur/occlusion -> feature noise -> keypoint jitter -> pose jitter"],
        "backup": ["这页可以和第 25 页呼应，不要讲太久。"],
    },
    31: {
        "time": "0.5 min",
        "script": "接下来进入 Kalman Filter。它的目的不是让单帧 PnP 更神奇，而是利用连续帧的运动规律，把当前观测和历史预测融合起来，降低随机抖动和异常帧的影响。",
        "board": ["Kalman = prediction + measurement update"],
        "backup": ["章节页快速过渡。"],
    },
    32: {
        "time": "2 min",
        "script": "Kalman 的一句话直觉是：上一帧帮助预测下一帧。预测步根据上一帧的位置、速度和运动模型，估计当前状态应该在哪里；观测步来自当前帧的 YOLOv8-Pose 加 PnP；更新步把预测和观测融合。如果当前观测很 noisy，滤波器会更相信预测；如果预测不确定而观测可靠，滤波器会更相信观测。",
        "board": ["prediction: previous state -> current estimate", "measurement: YOLO + PnP -> observed pose", "update: fuse prediction and measurement"],
        "backup": ["这页讲直觉，不写矩阵推导。"],
    },
    33: {
        "time": "3 min",
        "script": "这一页写 Kalman 基本公式，但不做完整推导。x 是状态，可以包含位置和速度，也可以扩展到姿态参数；F 是运动模型；z 是当前观测，也就是 PnP 给出的位姿；H 把状态映射到观测空间；K 是 Kalman gain，它决定当前时刻更相信预测还是更相信观测。直觉上，Kalman 不是简单平均，而是带不确定性权重的动态融合。",
        "board": ["Prediction:  x̂_k^- = F x̂_{k-1}", "Innovation:  y_k = z_k - H x̂_k^-", "Update:      x̂_k = x̂_k^- + K_k y_k"],
        "backup": ["如果被追问 Q 和 R：Q 表示过程噪声，R 表示观测噪声。"],
    },
    34: {
        "time": "2 min",
        "script": "Kalman 可以放在不同层级。滤 2D 层可以平滑检测框中心或关键点坐标，直观但要处理关键点可见性和对应关系。滤 6D 位姿层是在 PnP 后直接对 R 和 t 做平滑，能直接改善 pose jitter，也更适合第一版 baseline。我的建议是先做 6D 位姿层滤波，把效果和评价指标跑通，再考虑更复杂的 2D 层滤波。",
        "board": ["Option A: filter 2D keypoints p_i(t)", "Option B: filter 6D pose T_C^O(t)", "baseline: PnP -> Kalman on pose"],
        "backup": ["姿态滤波可以先用平移加 yaw，后续再扩展四元数。"],
    },
    35: {
        "time": "0.5 min",
        "script": "最后进入项目 pipeline 和评估。前面讲的是方法模块，这一章把它们串成工程闭环：训练阶段用动捕提供真值和标签，在线阶段用相机图像实时输出稳定 6D 位姿。",
        "board": ["training pipeline + online pipeline"],
        "backup": ["章节页快速过渡。"],
    },
    36: {
        "time": "2 min",
        "script": "训练阶段中，动捕既是老师，也是评估裁判。采集图像时同步记录动捕位姿，通过相机标定和坐标转换，把动捕世界坐标下的真值变成相机图像下的关键点标签。这样就能自动生成 YOLOv8-Pose 的训练数据。标定质量、时间同步和刚体外参会直接影响标签质量，所以这是整个数据闭环的关键。",
        "board": ["image + mocap pose + calibration -> auto labels", "labels -> train YOLOv8-Pose"],
        "backup": ["可补充 20 个 session、光照、背景、距离和角度覆盖。"],
    },
    37: {
        "time": "2 min",
        "script": "在线阶段中，相机每来一帧 RGB 图像，YOLOv8-Pose 先输出二维关键点；系统筛掉低置信度或不可用点，把剩余 2D-3D 对应送入 PnP；PnP 输出单帧 R 和 t；最后 Kalman 把当前观测和历史运动状态融合，得到更稳定的 6D pose。这个阶段不仅要看精度，还要看 FPS、latency 和连续稳定性。",
        "board": ["RGB_t -> YOLO -> p_t", "(p_t, P^O, K) -> PnP -> T_raw(t)", "Kalman: T_raw(t) -> T_smooth(t)"],
        "backup": ["这里可以引出海康工业相机、全局快门、短曝光和实时采集。"],
    },
    38: {
        "time": "2 min",
        "script": "最后用三句话总结。第一，YOLOv8-Pose 在本项目中解决的是二维关键点检测，不是直接输出 6D 位姿。第二，二维关键点、三维模型点和相机内参通过 PnP 联系起来，才能求出 R 和 t。第三，快速运动真正难的是时序稳定，因为模糊、遮挡和视角变化会让关键点和 PnP 结果抖动，所以需要 Kalman Filter 和更完整的动态评价指标。最后我用一个问题收束：如果检测框很准，为什么位姿仍然可能不稳定？答案就是关键点误差和时序误差仍然会沿着几何链路传导。",
        "board": ["YOLOv8-Pose: image -> 2D keypoints", "PnP: 2D-3D correspondences -> R,t", "Kalman: raw pose sequence -> stable pose sequence"],
        "backup": ["问答时优先回到重投影误差、坐标系转换和 Kalman gain。"],
    },
}


if __name__ == "__main__":
    main()
