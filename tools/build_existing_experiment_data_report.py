from __future__ import annotations

import csv
import itertools
import json
import math
import statistics
import struct
import zipfile
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs" / "experiment_data_existing"
CHART_DIR = OUT_DIR / "charts"

DATASET_SUMMARY = ROOT / "outputs" / "datasets" / "uav_4m_20sessions_pose_20260413_v1_clean" / "split_summary.json"
DATASET_YAML = ROOT / "outputs" / "datasets" / "uav_4m_20sessions_pose_20260413_v1_clean" / "dataset.yaml"
TRAIN_RESULTS = ROOT / "outputs" / "train_runs" / "uav_4m_20sessions_pose_v1" / "results.csv"
TRAIN_ARGS = ROOT / "outputs" / "train_runs" / "uav_4m_20sessions_pose_v1" / "args.yaml"
BEST_WEIGHT = ROOT / "outputs" / "train_runs" / "uav_4m_20sessions_pose_v1" / "weights" / "best.pt"
LIVE_LOG = ROOT / "outputs" / "live_pose_log_v1.csv"
FZMOTION_LOG = ROOT / "outputs" / "fzmotion_pose_log.csv"
MODEL_JSON = ROOT / "models" / "car_custom_keypoints_12_migrated_200xx_exact.json"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def to_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def stdev(values: list[float]) -> float | None:
    return statistics.pstdev(values) if values else None


def fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "无可用数据"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def parse_session_name(name: str) -> dict[str, str]:
    # 文件夹命名形如 uav_4m_reshoot_d30_bgA_lightOn。
    parts = name.split("_")
    info = {"session": name, "distance_m": "", "background": "", "light": ""}
    for part in parts:
        if part.startswith("d") and part[1:].isdigit():
            info["distance_m"] = f"{int(part[1:]) / 10:.1f}"
        elif part in {"bgA", "bgB"}:
            info["background"] = part
        elif part in {"lightOn", "lightOff"}:
            info["light"] = part
    return info


def load_training_rows() -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for row in read_csv_dicts(TRAIN_RESULTS):
        clean: dict[str, float] = {}
        for key, value in row.items():
            if key is None:
                continue
            clean[key.strip()] = float(value)
        rows.append(clean)
    return rows


def summarize_training(rows: list[dict[str, float]]) -> dict[str, Any]:
    if not rows:
        return {}
    for row in rows:
        row["train/total_loss"] = sum(row.get(k, 0.0) for k in [
            "train/box_loss",
            "train/pose_loss",
            "train/kobj_loss",
            "train/cls_loss",
            "train/dfl_loss",
        ])
        row["val/total_loss"] = sum(row.get(k, 0.0) for k in [
            "val/box_loss",
            "val/pose_loss",
            "val/kobj_loss",
            "val/cls_loss",
            "val/dfl_loss",
        ])
    best_pose = max(rows, key=lambda x: x.get("metrics/mAP50-95(P)", float("-inf")))
    final = rows[-1]
    return {
        "epochs_recorded": len(rows),
        "final_epoch": int(final["epoch"]),
        "training_time_h": final.get("time", 0.0) / 3600.0,
        "best_pose_epoch": int(best_pose["epoch"]),
        "best_pose_map50": best_pose.get("metrics/mAP50(P)"),
        "best_pose_map50_95": best_pose.get("metrics/mAP50-95(P)"),
        "best_box_map50": best_pose.get("metrics/mAP50(B)"),
        "best_box_map50_95": best_pose.get("metrics/mAP50-95(B)"),
        "best_pose_precision": best_pose.get("metrics/precision(P)"),
        "best_pose_recall": best_pose.get("metrics/recall(P)"),
        "final_train_total_loss": final.get("train/total_loss"),
        "final_val_total_loss": final.get("val/total_loss"),
        "final_train_pose_loss": final.get("train/pose_loss"),
        "final_val_pose_loss": final.get("val/pose_loss"),
        "final_train_kobj_loss": final.get("train/kobj_loss"),
        "final_val_kobj_loss": final.get("val/kobj_loss"),
    }


def quat_norm(q: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(q)
    return q / norm if norm > 0 else q


def quat_angle_deg(q1: np.ndarray, q2: np.ndarray) -> float:
    q1 = quat_norm(q1)
    q2 = quat_norm(q2)
    dot = float(abs(np.dot(q1, q2)))
    dot = min(1.0, max(-1.0, dot))
    return math.degrees(2.0 * math.acos(dot))


def quat_to_rot(q: np.ndarray) -> np.ndarray:
    x, y, z, w = quat_norm(q)
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def model_points_and_diameter() -> tuple[np.ndarray | None, float | None]:
    if not MODEL_JSON.exists():
        return None, None
    payload = read_json(MODEL_JSON)
    points = np.array([p["xyz_m"] for p in payload.get("points", [])], dtype=float)
    if len(points) < 2:
        return points, None
    diameter = max(float(np.linalg.norm(a - b)) for a, b in itertools.combinations(points, 2))
    return points, diameter


def summarize_pose_eval() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = read_csv_dicts(FZMOTION_LOG)
    points, diameter = model_points_and_diameter()
    per_frame: list[dict[str, Any]] = []
    for row in rows:
        pred_t = np.array([to_float(row.get(f"prediction_t{axis}")) for axis in "xyz"], dtype=object)
        mocap_t = np.array([to_float(row.get(f"mocap_t{axis}")) for axis in "xyz"], dtype=object)
        pred_q = np.array([to_float(row.get(f"prediction_q{axis}")) for axis in "xyzw"], dtype=object)
        mocap_q = np.array([to_float(row.get(f"mocap_q{axis}")) for axis in "xyzw"], dtype=object)
        if any(v is None for v in pred_t) or any(v is None for v in mocap_t):
            continue
        if any(v is None for v in pred_q) or any(v is None for v in mocap_q):
            continue
        pred_t = pred_t.astype(float)
        mocap_t = mocap_t.astype(float)
        pred_q = pred_q.astype(float)
        mocap_q = mocap_q.astype(float)
        trans_cm = float(np.linalg.norm(pred_t - mocap_t) * 100.0)
        rot_deg = quat_angle_deg(pred_q, mocap_q)
        reproj = to_float(row.get("prediction_reproj_px"))
        add_cm = None
        add_ratio = None
        if points is not None and diameter:
            pred_pts = (quat_to_rot(pred_q) @ points.T).T + pred_t
            mocap_pts = (quat_to_rot(mocap_q) @ points.T).T + mocap_t
            add_m = float(np.mean(np.linalg.norm(pred_pts - mocap_pts, axis=1)))
            add_cm = add_m * 100.0
            add_ratio = add_m / diameter
        per_frame.append({
            "frame_index": int(float(row.get("frame_index", len(per_frame)))),
            "translation_error_cm": trans_cm,
            "rotation_error_deg": rot_deg,
            "reprojection_error_px": reproj,
            "add_error_cm": add_cm,
            "add_ratio": add_ratio,
        })

    trans = [x["translation_error_cm"] for x in per_frame]
    rot = [x["rotation_error_deg"] for x in per_frame]
    reproj = [x["reprojection_error_px"] for x in per_frame if x["reprojection_error_px"] is not None]
    add = [x["add_error_cm"] for x in per_frame if x["add_error_cm"] is not None]
    add_ratio = [x["add_ratio"] for x in per_frame if x["add_ratio"] is not None]
    both_good = [x for x in per_frame if x["translation_error_cm"] < 5.0 and x["rotation_error_deg"] < 5.0]
    add_good = [x for x in per_frame if x["add_ratio"] is not None and x["add_ratio"] < 0.10]
    summary = {
        "source": str(FZMOTION_LOG),
        "note": "这是现有的 10 帧旧动捕对齐样例日志，不是当前 20-session 数据集的完整测试集。",
        "num_frames": len(per_frame),
        "reprojection_mean_px": mean(reproj),
        "reprojection_median_px": median(reproj),
        "reprojection_std_px": stdev(reproj),
        "reprojection_recall_lt5px": len([x for x in reproj if x < 5.0]) / len(reproj) if reproj else None,
        "translation_mean_cm": mean(trans),
        "translation_median_cm": median(trans),
        "translation_std_cm": stdev(trans),
        "rotation_mean_deg": mean(rot),
        "rotation_median_deg": median(rot),
        "rotation_std_deg": stdev(rot),
        "recall_5cm_5deg": len(both_good) / len(per_frame) if per_frame else None,
        "add_mean_cm": mean(add),
        "add_median_cm": median(add),
        "add_std_cm": stdev(add),
        "add_recall_lt10pct_diameter": len(add_good) / len(add_ratio) if add_ratio else None,
        "object_diameter_m": diameter,
    }
    return summary, per_frame


def summarize_live_log() -> dict[str, Any]:
    rows = read_csv_dicts(LIVE_LOG)
    valid = []
    for row in rows:
        conf = to_float(row.get("prediction_confidence"))
        reproj = to_float(row.get("prediction_reproj_px"))
        ts = to_float(row.get("timestamp_s"))
        source = row.get("prediction_source") or ""
        if conf is not None and reproj is not None and ts is not None:
            valid.append({"conf": conf, "reproj": reproj, "ts": ts, "source": source})
    timestamps = [x["ts"] for x in valid]
    fps = None
    if len(timestamps) >= 2:
        duration = max(timestamps) - min(timestamps)
        fps = (len(timestamps) - 1) / duration if duration > 0 else None
    source_counts: dict[str, int] = {}
    for item in valid:
        source_counts[item["source"]] = source_counts.get(item["source"], 0) + 1
    reproj_values = [x["reproj"] for x in valid]
    conf_values = [x["conf"] for x in valid]
    return {
        "source": str(LIVE_LOG),
        "total_rows": len(rows),
        "valid_predictions": len(valid),
        "mean_fps_from_timestamp": fps,
        "confidence_mean": mean(conf_values),
        "confidence_median": median(conf_values),
        "reprojection_mean_px": mean(reproj_values),
        "reprojection_median_px": median(reproj_values),
        "reprojection_recall_lt5px": len([x for x in reproj_values if x < 5.0]) / len(reproj_values) if reproj_values else None,
        "source_counts": source_counts,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def save_charts(
    session_rows: list[dict[str, Any]],
    train_rows: list[dict[str, float]],
    live_summary: dict[str, Any],
    pose_summary: dict[str, Any],
    pose_frames: list[dict[str, Any]],
) -> list[Path]:
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    chart_paths: list[Path] = []

    names = [r["session"] for r in session_rows]
    counts = [int(r["saved_labels"]) for r in session_rows]
    plt.figure(figsize=(12, 8))
    colors = ["#2563eb" if "lightOn" in n else "#64748b" for n in names]
    plt.barh(range(len(names)), counts, color=colors)
    plt.yticks(range(len(names)), names, fontsize=8)
    plt.xlabel("Saved labels")
    plt.title("20-session label counts")
    plt.gca().invert_yaxis()
    plt.tight_layout()
    path = CHART_DIR / "01_session_label_counts.png"
    plt.savefig(path, dpi=180)
    plt.close()
    chart_paths.append(path)

    dist_counts: dict[str, int] = {}
    for row in session_rows:
        dist_counts[row["distance_m"]] = dist_counts.get(row["distance_m"], 0) + int(row["saved_labels"])
    plt.figure(figsize=(8, 4.5))
    xs = sorted(dist_counts.keys(), key=float)
    plt.bar(xs, [dist_counts[x] for x in xs], color="#16a34a")
    plt.xlabel("Distance (m)")
    plt.ylabel("Saved labels")
    plt.title("Dataset size by distance")
    plt.tight_layout()
    path = CHART_DIR / "02_distance_distribution.png"
    plt.savefig(path, dpi=180)
    plt.close()
    chart_paths.append(path)

    cond_counts: dict[str, int] = {}
    for row in session_rows:
        key = f"{row['background']}-{row['light']}"
        cond_counts[key] = cond_counts.get(key, 0) + int(row["saved_labels"])
    plt.figure(figsize=(8, 4.5))
    xs = list(cond_counts.keys())
    plt.bar(xs, [cond_counts[x] for x in xs], color=["#0f766e", "#0891b2", "#f97316", "#a16207"][: len(xs)])
    plt.ylabel("Saved labels")
    plt.title("Dataset size by background and light")
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    path = CHART_DIR / "03_condition_distribution.png"
    plt.savefig(path, dpi=180)
    plt.close()
    chart_paths.append(path)

    if train_rows:
        epochs = [r["epoch"] for r in train_rows]
        plt.figure(figsize=(10, 5.2))
        plt.plot(epochs, [r["train/total_loss"] for r in train_rows], label="train total", linewidth=2)
        plt.plot(epochs, [r["val/total_loss"] for r in train_rows], label="val total", linewidth=2)
        plt.plot(epochs, [r["train/pose_loss"] for r in train_rows], label="train pose L_pt", alpha=0.85)
        plt.plot(epochs, [r["val/pose_loss"] for r in train_rows], label="val pose L_pt", alpha=0.85)
        plt.plot(epochs, [r["train/kobj_loss"] for r in train_rows], label="train kobj L_conf", alpha=0.85)
        plt.plot(epochs, [r["val/kobj_loss"] for r in train_rows], label="val kobj L_conf", alpha=0.85)
        plt.xlabel("Epoch")
        plt.ylabel("Loss")
        plt.title("Training / validation losses")
        plt.legend(ncol=2, fontsize=8)
        plt.grid(alpha=0.25)
        plt.tight_layout()
        path = CHART_DIR / "04_training_validation_loss.png"
        plt.savefig(path, dpi=180)
        plt.close()
        chart_paths.append(path)

        plt.figure(figsize=(10, 5.2))
        plt.plot(epochs, [r["metrics/mAP50(B)"] for r in train_rows], label="Box mAP50", linewidth=2)
        plt.plot(epochs, [r["metrics/mAP50-95(B)"] for r in train_rows], label="Box mAP50-95", linewidth=2)
        plt.plot(epochs, [r["metrics/mAP50(P)"] for r in train_rows], label="Pose mAP50", linewidth=2)
        plt.plot(epochs, [r["metrics/mAP50-95(P)"] for r in train_rows], label="Pose mAP50-95", linewidth=2)
        plt.xlabel("Epoch")
        plt.ylabel("mAP")
        plt.title("Validation mAP curves")
        plt.ylim(0.75, 1.01)
        plt.legend(fontsize=8)
        plt.grid(alpha=0.25)
        plt.tight_layout()
        path = CHART_DIR / "05_map_curves.png"
        plt.savefig(path, dpi=180)
        plt.close()
        chart_paths.append(path)

        plt.figure(figsize=(10, 5.2))
        plt.plot(epochs, [r["metrics/precision(P)"] for r in train_rows], label="Pose precision", linewidth=2)
        plt.plot(epochs, [r["metrics/recall(P)"] for r in train_rows], label="Pose recall", linewidth=2)
        plt.plot(epochs, [r["metrics/precision(B)"] for r in train_rows], label="Box precision", linestyle="--")
        plt.plot(epochs, [r["metrics/recall(B)"] for r in train_rows], label="Box recall", linestyle="--")
        plt.xlabel("Epoch")
        plt.ylabel("Score")
        plt.title("Precision / recall curves")
        plt.ylim(0.90, 1.01)
        plt.legend(fontsize=8)
        plt.grid(alpha=0.25)
        plt.tight_layout()
        path = CHART_DIR / "06_precision_recall_curves.png"
        plt.savefig(path, dpi=180)
        plt.close()
        chart_paths.append(path)

    live_rows = read_csv_dicts(LIVE_LOG)
    live_valid = []
    for row in live_rows:
        idx = to_float(row.get("frame_index"))
        conf = to_float(row.get("prediction_confidence"))
        reproj = to_float(row.get("prediction_reproj_px"))
        if idx is not None and conf is not None and reproj is not None:
            live_valid.append((idx, conf, reproj))
    if live_valid:
        # 日志很长，这里抽样画趋势，避免图上点过密。
        step = max(1, len(live_valid) // 1200)
        sampled = live_valid[::step]
        xs = [x[0] for x in sampled]
        conf = [x[1] for x in sampled]
        reproj = [x[2] for x in sampled]
        fig, ax1 = plt.subplots(figsize=(10, 5.2))
        ax1.plot(xs, conf, color="#2563eb", label="confidence", linewidth=1.5)
        ax1.set_xlabel("Frame index")
        ax1.set_ylabel("Confidence", color="#2563eb")
        ax1.tick_params(axis="y", labelcolor="#2563eb")
        ax2 = ax1.twinx()
        ax2.plot(xs, reproj, color="#dc2626", label="reprojection px", linewidth=1.2, alpha=0.75)
        ax2.set_ylabel("Reprojection error (px)", color="#dc2626")
        ax2.tick_params(axis="y", labelcolor="#dc2626")
        plt.title("Live YOLO6D log: confidence and reprojection")
        fig.tight_layout()
        path = CHART_DIR / "07_live_log_confidence_reprojection.png"
        plt.savefig(path, dpi=180)
        plt.close()
        chart_paths.append(path)

    if pose_frames:
        frames = [x["frame_index"] for x in pose_frames]
        plt.figure(figsize=(10, 5.2))
        plt.plot(frames, [x["translation_error_cm"] for x in pose_frames], marker="o", label="translation error (cm)")
        plt.plot(frames, [x["rotation_error_deg"] for x in pose_frames], marker="s", label="rotation error (deg)")
        if any(x["reprojection_error_px"] is not None for x in pose_frames):
            plt.plot(frames, [x["reprojection_error_px"] for x in pose_frames], marker="^", label="reprojection error (px)")
        plt.xlabel("Frame index")
        plt.title("Existing mocap comparison sample")
        plt.legend(fontsize=8)
        plt.grid(alpha=0.25)
        plt.tight_layout()
        path = CHART_DIR / "08_existing_mocap_error_sample.png"
        plt.savefig(path, dpi=180)
        plt.close()
        chart_paths.append(path)

    return chart_paths


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n":
        return 1200, 800
    return struct.unpack(">II", header[16:24])


def p(text: str = "", style: str = "Normal") -> str:
    style_xml = "" if style == "Normal" else f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>'
    return f"<w:p>{style_xml}<w:r><w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"


def bullet(text: str) -> str:
    return (
        '<w:p><w:pPr><w:pStyle w:val="ListParagraph"/>'
        '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>'
        f'<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'
    )


def table(rows: list[list[Any]], header: bool = True) -> str:
    xml = [
        '<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/>'
        '<w:tblW w:w="0" w:type="auto"/>'
        '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/>'
        '</w:tblPr><w:tblGrid/>'
    ]
    for idx, row in enumerate(rows):
        xml.append("<w:tr>")
        for cell in row:
            shade = '<w:shd w:fill="D9EAF7"/>' if header and idx == 0 else ""
            bold_start = "<w:b/>" if header and idx == 0 else ""
            xml.append(
                "<w:tc><w:tcPr>"
                '<w:tcMar><w:top w:w="120" w:type="dxa"/><w:left w:w="120" w:type="dxa"/><w:bottom w:w="120" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tcMar>'
                f"{shade}</w:tcPr><w:p><w:r><w:rPr>{bold_start}</w:rPr>"
                f'<w:t xml:space="preserve">{escape(str(cell))}</w:t></w:r></w:p></w:tc>'
            )
        xml.append("</w:tr>")
    xml.append("</w:tbl>")
    return "".join(xml)


def image_paragraph(rid: str, path: Path, width_in: float = 6.4) -> str:
    width_px, height_px = png_size(path)
    cx = int(width_in * 914400)
    cy = int(cx * height_px / max(width_px, 1))
    return f"""
<w:p>
  <w:r>
    <w:drawing>
      <wp:inline distT="0" distB="0" distL="0" distR="0" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">
        <wp:extent cx="{cx}" cy="{cy}"/>
        <wp:docPr id="{rid[3:]}" name="{escape(path.stem)}"/>
        <a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
          <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
            <pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
              <pic:nvPicPr><pic:cNvPr id="0" name="{escape(path.name)}"/><pic:cNvPicPr/></pic:nvPicPr>
              <pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
              <pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>
            </pic:pic>
          </a:graphicData>
        </a:graphic>
      </wp:inline>
    </w:drawing>
  </w:r>
</w:p>
"""


def build_docx(
    report_path: Path,
    dataset_summary: dict[str, Any],
    session_rows: list[dict[str, Any]],
    training_summary: dict[str, Any],
    live_summary: dict[str, Any],
    pose_summary: dict[str, Any],
    charts: list[Path],
) -> None:
    image_rels = {chart: f"rId{idx + 10}" for idx, chart in enumerate(charts)}
    body: list[str] = []
    body.append(p("YOLO6D 小车实验数据清单（已有数据版）", "Title"))
    body.append(p("根据当前 D:\\YOLO6D_Car 项目中已经存在的数据、标签、训练输出和日志自动汇总。", "Subtitle"))
    body.append(p("一、数据集总览", "Heading1"))
    body.append(table([
        ["项目", "数值"],
        ["数据集目录", dataset_summary.get("dataset_dir", "")],
        ["总图像/标签数", fmt(dataset_summary.get("num_total"))],
        ["训练集", fmt(dataset_summary.get("num_train"))],
        ["验证集", fmt(dataset_summary.get("num_val"))],
        ["关键点数量", fmt(dataset_summary.get("num_keypoints"))],
        ["类别", dataset_summary.get("class_name", "car_model")],
        ["划分比例", f"val_ratio={dataset_summary.get('val_ratio')}, seed={dataset_summary.get('seed')}"],
    ]))
    body.append(p("二、20 个采集 session 标签数量", "Heading1"))
    body.append(p("采集维度包含距离 1.0/2.0/3.0/3.5/4.0 m，背景 bgA/bgB，光照 lightOn/lightOff。"))
    body.append(table([["Session", "距离/m", "背景", "光照", "保存标签数"]] + [
        [r["session"], r["distance_m"], r["background"], r["light"], fmt(int(r["saved_labels"]))] for r in session_rows
    ]))
    body.append(p("三、训练设置与验证指标", "Heading1"))
    body.append(table([
        ["项目", "数值"],
        ["训练 run", str(ROOT / "outputs" / "train_runs" / "uav_4m_20sessions_pose_v1")],
        ["权重", str(BEST_WEIGHT)],
        ["dataset.yaml", str(DATASET_YAML)],
        ["记录 epoch 数", fmt(training_summary.get("epochs_recorded"))],
        ["最终 epoch", fmt(training_summary.get("final_epoch"))],
        ["训练耗时/h", fmt(training_summary.get("training_time_h"), 2)],
        ["最佳 Pose mAP50 epoch", fmt(training_summary.get("best_pose_epoch"))],
        ["Pose mAP50", fmt(training_summary.get("best_pose_map50"), 4)],
        ["Pose mAP50-95", fmt(training_summary.get("best_pose_map50_95"), 4)],
        ["Box mAP50", fmt(training_summary.get("best_box_map50"), 4)],
        ["Box mAP50-95", fmt(training_summary.get("best_box_map50_95"), 4)],
        ["Pose Precision / Recall", f"{fmt(training_summary.get('best_pose_precision'), 4)} / {fmt(training_summary.get('best_pose_recall'), 4)}"],
        ["最终 train total loss", fmt(training_summary.get("final_train_total_loss"), 4)],
        ["最终 val total loss", fmt(training_summary.get("final_val_total_loss"), 4)],
        ["最终 train L_pt / L_conf", f"{fmt(training_summary.get('final_train_pose_loss'), 4)} / {fmt(training_summary.get('final_train_kobj_loss'), 4)}"],
        ["最终 val L_pt / L_conf", f"{fmt(training_summary.get('final_val_pose_loss'), 4)} / {fmt(training_summary.get('final_val_kobj_loss'), 4)}"],
    ]))
    body.append(p("四、已有实时日志统计", "Heading1"))
    body.append(table([
        ["项目", "数值"],
        ["日志文件", live_summary.get("source", "")],
        ["总行数", fmt(live_summary.get("total_rows"))],
        ["有效预测帧", fmt(live_summary.get("valid_predictions"))],
        ["由 timestamp 估计的平均 FPS", fmt(live_summary.get("mean_fps_from_timestamp"), 2)],
        ["平均置信度", fmt(live_summary.get("confidence_mean"), 4)],
        ["中位置信度", fmt(live_summary.get("confidence_median"), 4)],
        ["平均重投影误差/px", fmt(live_summary.get("reprojection_mean_px"), 3)],
        ["重投影误差中位数/px", fmt(live_summary.get("reprojection_median_px"), 3)],
        ["重投影误差 <5px 比例", fmt(live_summary.get("reprojection_recall_lt5px"), 4)],
    ]))
    body.append(p("五、已有动捕对齐样例统计", "Heading1"))
    body.append(p(str(pose_summary.get("note", ""))))
    body.append(table([
        ["指标", "数值"],
        ["样例帧数", fmt(pose_summary.get("num_frames"))],
        ["2D 重投影均值/中位数/std px", f"{fmt(pose_summary.get('reprojection_mean_px'))} / {fmt(pose_summary.get('reprojection_median_px'))} / {fmt(pose_summary.get('reprojection_std_px'))}"],
        ["2D recall <5px", fmt(pose_summary.get("reprojection_recall_lt5px"), 4)],
        ["平移误差均值/中位数/std cm", f"{fmt(pose_summary.get('translation_mean_cm'))} / {fmt(pose_summary.get('translation_median_cm'))} / {fmt(pose_summary.get('translation_std_cm'))}"],
        ["旋转误差均值/中位数/std deg", f"{fmt(pose_summary.get('rotation_mean_deg'))} / {fmt(pose_summary.get('rotation_median_deg'))} / {fmt(pose_summary.get('rotation_std_deg'))}"],
        ["5cm 且 5deg recall", fmt(pose_summary.get("recall_5cm_5deg"), 4)],
        ["ADD 均值/中位数/std cm", f"{fmt(pose_summary.get('add_mean_cm'))} / {fmt(pose_summary.get('add_median_cm'))} / {fmt(pose_summary.get('add_std_cm'))}"],
        ["ADD <10% 物体直径 recall", fmt(pose_summary.get("add_recall_lt10pct_diameter"), 4)],
        ["模型点云直径/m", fmt(pose_summary.get("object_diameter_m"), 4)],
    ]))
    body.append(p("注意：这一组 6DoF 误差来自已有旧日志，只能说明当前工程中已有可计算样例；如果要作为最终实验表格，应重新用当前 v1 权重、当前相机外参和测试序列生成 prediction-vs-mocap 评估日志。"))
    body.append(p("六、可视化图表", "Heading1"))
    for chart in charts:
        body.append(p(chart.stem.replace("_", " "), "Heading2"))
        body.append(image_paragraph(image_rels[chart], chart))
    body.append('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>')

    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>{''.join(body)}</w:body>
</w:document>
"""
    rels = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
    ]
    for chart, rid in image_rels.items():
        rels.append(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{escape(chart.name)}"/>')
    rels.append("</Relationships>")
    rels_xml = "".join(rels)
    styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:hAnsi="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:sz w:val="21"/></w:rPr><w:pPr><w:spacing w:after="120" w:line="300" w:lineRule="auto"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="34"/><w:color w:val="17365D"/></w:rPr><w:pPr><w:spacing w:after="240"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/><w:rPr><w:sz w:val="22"/><w:color w:val="666666"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="28"/><w:color w:val="1F4E79"/></w:rPr><w:pPr><w:spacing w:before="280" w:after="160"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="23"/><w:color w:val="2F75B5"/></w:rPr><w:pPr><w:spacing w:before="180" w:after="120"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:style>
  <w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:tblPr><w:tblBorders><w:top w:val="single" w:sz="4" w:color="BFBFBF"/><w:left w:val="single" w:sz="4" w:color="BFBFBF"/><w:bottom w:val="single" w:sz="4" w:color="BFBFBF"/><w:right w:val="single" w:sz="4" w:color="BFBFBF"/><w:insideH w:val="single" w:sz="4" w:color="D9D9D9"/><w:insideV w:val="single" w:sz="4" w:color="D9D9D9"/></w:tblBorders></w:tblPr></w:style>
</w:styles>
"""
    numbering_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum>
  <w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
</w:numbering>
"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
</Types>
"""
    package_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(report_path, "w", compression=zipfile.ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", content_types)
        docx.writestr("_rels/.rels", package_rels)
        docx.writestr("word/document.xml", document_xml)
        docx.writestr("word/styles.xml", styles_xml)
        docx.writestr("word/numbering.xml", numbering_xml)
        docx.writestr("word/_rels/document.xml.rels", rels_xml)
        for chart in charts:
            docx.write(chart, f"word/media/{chart.name}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dataset_summary = read_json(DATASET_SUMMARY)
    session_rows: list[dict[str, Any]] = []
    for session, count in dataset_summary.get("per_session_counts", {}).items():
        row = parse_session_name(session)
        row["saved_labels"] = count
        summary_path = ROOT / "outputs" / "auto_labels" / session / "summary.json"
        if summary_path.exists():
            summary = read_json(summary_path)
            counts = summary.get("counts", {})
            row["raw_total_rows"] = counts.get("total_rows", "")
            row["raw_saved_labels"] = counts.get("saved_labels", "")
        session_rows.append(row)
    session_rows.sort(key=lambda x: (float(x["distance_m"]), x["background"], x["light"]))

    train_rows = load_training_rows()
    training_summary = summarize_training(train_rows)
    live_summary = summarize_live_log()
    pose_summary, pose_frames = summarize_pose_eval()
    charts = save_charts(session_rows, train_rows, live_summary, pose_summary, pose_frames)

    write_csv(OUT_DIR / "session_statistics.csv", session_rows)
    write_csv(OUT_DIR / "training_metrics_summary.csv", [training_summary])
    write_csv(OUT_DIR / "live_pose_log_v1_summary.csv", [live_summary])
    write_csv(OUT_DIR / "existing_pose_eval_summary.csv", [pose_summary])
    write_csv(OUT_DIR / "existing_pose_eval_per_frame.csv", pose_frames)
    (OUT_DIR / "experiment_data_summary.json").write_text(
        json.dumps(
            {
                "dataset_summary": dataset_summary,
                "training_summary": training_summary,
                "live_summary": live_summary,
                "existing_pose_eval_summary": pose_summary,
                "charts": [str(p) for p in charts],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    build_docx(
        OUT_DIR / "实验数据清单_已有数据版.docx",
        dataset_summary,
        session_rows,
        training_summary,
        live_summary,
        pose_summary,
        charts,
    )
    print(json.dumps({
        "output_dir": str(OUT_DIR),
        "docx": str(OUT_DIR / "实验数据清单_已有数据版.docx"),
        "charts": [str(p) for p in charts],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
