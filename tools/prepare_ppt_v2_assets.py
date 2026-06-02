from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "outputs" / "lecture_handout_work" / "ppt_v2_assets"


TAKEAWAYS: dict[int, str] = {
    1: "核心结论：本项目不是单帧检测，而是“2D关键点 + PnP + Kalman”的快速运动 6D 位姿估计系统。",
    2: "核心结论：整场汇报按“问题定义 → 网络前端 → 几何求解 → 动态稳定 → 系统评估”的因果链展开。",
    3: "核心结论：检测框只能回答图像中的位置，6D 位姿才能回答三维空间中的距离、朝向和运动关系。",
    4: "核心结论：Detection 找目标，Tracking 保连续，Pose Estimation 给出三维位置和朝向。",
    5: "核心结论：2D box 是像素区域；6D pose 是相机坐标系与目标坐标系之间的刚体变换。",
    6: "核心结论：无人机视觉链路需要从“找到目标”进一步走到“稳定理解空间关系”。",
    7: "核心结论：YOLOv8-Pose 是关键点检测前端，最终 6D 位姿仍由几何后端求解。",
    8: "核心结论：图像对网络来说是 RGB 张量，图像质量会直接影响关键点回归质量。",
    9: "核心结论：快速运动首先破坏边缘、角点和纹理，再传导到关键点与位姿。",
    10: "核心结论：YOLOv8-Pose 输出的是 box、2D keypoints 和 confidence，不直接输出 R、t。",
    11: "核心结论：Detect 只给框；Pose 额外给关键点，因此才能连接到后续 PnP 几何。",
    12: "核心结论：每个小车关键点必须有固定物理身份，否则 2D-3D 对应关系会错。",
    13: "核心结论：标签质量决定关键点稳定性；box 定位目标，keypoints 描述结构。",
    14: "核心结论：PnP 是从二维关键点走向三维位姿的几何桥梁。",
    15: "核心结论：同一个物理点必须同时拥有正确的 2D 像素坐标和 3D 模型坐标。",
    16: "核心结论：PnP 输入 2D-3D 对应点和内参 K，输出目标相对相机的 R、t。",
    17: "核心结论：投影公式描述 3D 点如何经过位姿和相机内参落到像素平面。",
    18: "核心结论：K 描述相机成像方式；换相机、镜头或分辨率后都要重新确认内参。",
    19: "核心结论：PnP 寻找的是让重投影误差最小的 R、t。",
    20: "核心结论：位姿一定属于两个坐标系之间，坐标系没对齐，标签和评估都会错。",
    21: "核心结论：动捕给世界坐标下的刚体位姿，图像/PnP 需要相机坐标下的物体位姿。",
    22: "核心结论：T_A^B 表示把 B 坐标系中的点变换到 A 坐标系，方向不能写反。",
    23: "核心结论：动捕真值必须通过链式变换转到相机光学坐标系下，才能和图像对齐。",
    24: "核心结论：相机动捕刚体到相机光学坐标系之间存在固定外参，换结构要重标定。",
    25: "核心结论：快速运动误差会从图像层逐级传到关键点、PnP 和跟踪输出。",
    26: "核心结论：运动模糊来自曝光期间目标位移，短曝光和补光是关键工程取舍。",
    27: "核心结论：视角、尺度和遮挡变化会降低连续帧之间的观测一致性。",
    28: "核心结论：几像素关键点抖动经过 PnP 后可能放大成明显的姿态抖动。",
    29: "核心结论：高 mAP 不等于位姿稳定，fast-moving 还要看抖动、延迟和连续性。",
    30: "核心结论：真正要解决的是完整误差链，而不是单独优化 detector。",
    31: "核心结论：Kalman 的作用是把历史运动预测和当前观测融合起来。",
    32: "核心结论：预测、观测、更新三步共同降低异常帧和随机抖动的影响。",
    33: "核心结论：Kalman gain 决定当前时刻更相信预测还是更相信观测。",
    34: "核心结论：第一版 baseline 更适合先滤 6D 位姿层，清晰、直接、可评估。",
    35: "核心结论：训练闭环和在线闭环共同决定最终 demo 质量。",
    36: "核心结论：动捕既提供训练真值，也提供评估基准；标定质量决定标签质量。",
    37: "核心结论：在线系统最终要同时满足精度、FPS、延迟和位姿连续性。",
    38: "核心结论：YOLO 负责关键点，PnP 负责几何位姿，Kalman 负责快速运动下的时序稳定。",
}


FORMULAS: dict[int, list[str]] = {
    17: [
        r"$P_i^C = R_C^O P_i^O + t_C^O$",
        r"$s\,[u_i,\ v_i,\ 1]^T = K\,[R_C^O\ |\ t_C^O]\,[X_i,\ Y_i,\ Z_i,\ 1]^T$",
    ],
    18: [r"$K=[\,f_x\ \ 0\ \ c_x;\ \ 0\ \ f_y\ \ c_y;\ \ 0\ \ 0\ \ 1\,]$"],
    19: [
        r"$e_i = p_i-\pi\!\left(K(RP_i^O+t)\right)$",
        r"$\min_{R,t}\sum_i \left\|e_i\right\|_2^2$",
    ],
    22: [
        r"$T_A^B=[\,R_A^B\ \ t_A^B;\ \ 0^T\ \ 1\,]$",
        r"$P^A=T_A^B P^B,\qquad T_A^C=T_A^B T_B^C$",
    ],
    23: [
        r"$T_C^O=T_C^W\,T_W^{B_o}\,T_{B_o}^{O}$",
        r"$P^C=T_C^O P^O$",
    ],
    24: [
        r"$T_W^C=T_W^{B_c}\,T_{B_c}^{C}$",
        r"$T_C^W=(T_W^C)^{-1}$",
    ],
    26: [r"$L_{\rm blur}\approx v_{\rm img}\,T_{\rm exp}$"],
    28: [
        r"$\Delta \xi \approx J^\dagger\Delta u$",
        r"$J_R=\cos^{-1}\!\left(\frac{{\rm trace}(R_{t-1}^{T}R_t)-1}{2}\right)$",
    ],
    29: [r"$\mathrm{mAP}\uparrow \;\nRightarrow\; \mathrm{stable\ 6D\ pose}$"],
    33: [
        r"$\hat{x}_{k}^{-}=F\hat{x}_{k-1}+Bu_k$",
        r"$K_k=P_k^-H^T(HP_k^-H^T+R)^{-1}$",
        r"$\hat{x}_k=\hat{x}_k^-+K_k(z_k-H\hat{x}_k^-)$",
    ],
    34: [r"$z_t=[x_t,y_t,z_t,\psi_t]^T,\quad x_t=[x,y,z,v_x,v_y,v_z,\psi,\dot{\psi}]^T$"],
    36: [r"$u_k^{gt}=\pi\!\left(K(R_C^{O,gt}X_k+t_C^{O,gt})\right)$"],
    37: [
        r"$I_t\rightarrow p_t,\qquad (p_t,P^O,K)\rightarrow T_{\rm raw}(t)$",
        r"$\mathrm{Kalman}:T_{\rm raw}(t)\rightarrow T_{\rm smooth}(t)$",
    ],
}


def render_formula_block(slide_index: int, formulas: list[str]) -> str:
    out = WORK / "formula_png"
    out.mkdir(parents=True, exist_ok=True)
    fig_h = max(0.45 * len(formulas), 0.8)
    fig, ax = plt.subplots(figsize=(8.8, fig_h), dpi=180)
    fig.patch.set_alpha(0)
    ax.set_axis_off()
    for i, formula in enumerate(formulas):
        y = 1.0 - (i + 0.62) / len(formulas)
        ax.text(
            0.02,
            y,
            formula,
            color="#22D3EE",
            fontsize=18,
            fontfamily="DejaVu Sans",
            va="center",
        )
    path = out / f"slide_{slide_index:02d}_formula.png"
    fig.savefig(path, transparent=True, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return str(path)


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    payload = []
    for index in range(1, 39):
        item = {
            "slide": index,
            "takeaway": TAKEAWAYS[index],
            "formula_image": None,
            "has_formula": index in FORMULAS,
        }
        if index in FORMULAS:
            item["formula_image"] = render_formula_block(index, FORMULAS[index])
        payload.append(item)

    json_path = WORK / "ppt_v2_additions.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json_path)


if __name__ == "__main__":
    main()
