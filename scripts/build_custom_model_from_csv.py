"""根据 FzMotion CSV 中的 marker 位置构建自定义模型 JSON。"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
# 支持直接运行脚本，不要求把 src 安装成 site-package。
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.transforms import quaternion_to_matrix


@dataclass(slots=True)
class FzCsvLayout:
    """缓存 FzMotion CSV 的列布局，避免每行重复解析表头。"""

    unit_scale_to_m: float
    rigid_rotation_cols: dict[str, int]
    rigid_position_cols: dict[str, int]
    marker_position_cols: dict[str, dict[str, int]]
    data_rows: list[list[str]]


def _normalize_row(row: list[str]) -> list[str]:
    """清理 CSV 单元格两端空白。"""
    return [cell.strip() for cell in row]


def _cell(row: list[str], index: int) -> str:
    """安全读取 CSV 单元格，列缺失时返回空字符串。"""
    if 0 <= index < len(row):
        return row[index].strip()
    return ""


def _length_unit_scale_to_m(length_units: str) -> float:
    """把 FzMotion 导出的长度单位转换成米。"""
    units = length_units.strip().lower()
    if units in {"m", "meter", "meters"}:
        return 1.0
    if units in {"cm", "centimeter", "centimeters"}:
        return 0.01
    if units in {"mm", "millimeter", "millimeters"}:
        return 0.001
    raise ValueError(f"Unsupported FzMotion length unit: {length_units}")


def parse_args() -> argparse.Namespace:
    """定义从 marker 轨迹生成自定义 3D 关键点模型的参数。"""
    parser = argparse.ArgumentParser(description="Build a custom car model JSON from FzMotion CSV markers.")
    parser.add_argument("--csv-path", required=True, help="FzMotion CSV containing Rigid0 and marker world positions.")
    parser.add_argument("--rigid-body", default="Rigid0", help="Rigid body name that defines the local frame.")
    parser.add_argument("--marker-ids", nargs="+", required=True, help="Marker IDs or names to convert into local model points.")
    parser.add_argument(
        "--point-names",
        nargs="+",
        default=None,
        help="Optional output point names. Must match marker count when provided.",
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / "models" / "car_custom_keypoints.json"),
        help="Output JSON path.",
    )
    parser.add_argument(
        "--report-out",
        default=str(ROOT / "outputs" / "calibration" / "car_custom_keypoints_report.json"),
        help="Output JSON report path.",
    )
    return parser.parse_args()


def _load_fzmotion_layout(csv_path: Path, rigid_body: str) -> FzCsvLayout:
    """解析 FzMotion 表头，找到刚体和 marker 的 Rotation/Position 列。"""
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = [row for row in csv.reader(handle) if any(cell.strip() for cell in row)]

    if not rows or _normalize_row(rows[0])[0] != "DataName":
        raise ValueError("Expected an FzMotion CSV export.")

    metadata_row = _normalize_row(rows[0])
    metadata: dict[str, str] = {}
    for idx in range(0, len(metadata_row) - 1, 2):
        key = metadata_row[idx]
        value = metadata_row[idx + 1]
        if key:
            metadata[key] = value

    unit_scale = _length_unit_scale_to_m(metadata.get("LengthUnits", "mm"))

    type_row = _normalize_row(rows[1])
    name_row = _normalize_row(rows[2])
    semantic_row = _normalize_row(rows[4])
    axis_row = _normalize_row(rows[5])
    max_cols = max(len(type_row), len(name_row), len(semantic_row), len(axis_row))

    rigid_rotation_cols: dict[str, int] = {}
    rigid_position_cols: dict[str, int] = {}
    marker_position_cols: dict[str, dict[str, int]] = {}

    for col in range(max_cols):
        entity_type = _cell(type_row, col)
        entity_name = _cell(name_row, col)
        semantic = _cell(semantic_row, col)
        axis = _cell(axis_row, col).upper()

        if entity_type == "Rigid Body" and entity_name == rigid_body:
            if semantic == "Rotation" and axis in {"X", "Y", "Z", "W"}:
                rigid_rotation_cols[axis] = col
            elif semantic == "Position" and axis in {"X", "Y", "Z"}:
                rigid_position_cols[axis] = col

        if entity_type in {"Marker", "RigidBodyMarker"} and entity_name:
            if semantic == "Position" and axis in {"X", "Y", "Z"}:
                # Marker 名称在不同导出里可能是 Marker001、001 或 1，这里统一建别名。
                aliases = {entity_name}

                if "Marker" in entity_name:
                    after_marker = entity_name.split("Marker")[-1]
                    if after_marker:
                        aliases.add(after_marker)
                        aliases.add(after_marker.lstrip("0") or "0")

                trailing_digits = "".join(ch for ch in entity_name if ch.isdigit())
                if trailing_digits:
                    aliases.add(trailing_digits)
                    aliases.add(trailing_digits.lstrip("0") or "0")

                for alias in aliases:
                    marker_position_cols.setdefault(alias, {})[axis] = col

    if not {"X", "Y", "Z", "W"}.issubset(rigid_rotation_cols):
        raise ValueError(f"Rigid body {rigid_body} is missing rotation columns.")
    if not {"X", "Y", "Z"}.issubset(rigid_position_cols):
        raise ValueError(f"Rigid body {rigid_body} is missing position columns.")

    return FzCsvLayout(
        unit_scale_to_m=unit_scale,
        rigid_rotation_cols=rigid_rotation_cols,
        rigid_position_cols=rigid_position_cols,
        marker_position_cols=marker_position_cols,
        data_rows=rows[6:],
    )


def _try_float(text: str) -> float | None:
    """把 CSV 文本安全转成 float，空值或非法值返回 None。"""
    text = text.strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _extract_vector(row: list[str], cols: dict[str, int]) -> np.ndarray | None:
    """按 X/Y/Z 列提取三维向量。"""
    values: list[float] = []
    for axis in ("X", "Y", "Z"):
        value = _try_float(_cell(row, cols[axis]))
        if value is None:
            return None
        values.append(value)
    return np.asarray(values, dtype=np.float64)


def _extract_quaternion(row: list[str], cols: dict[str, int]) -> np.ndarray | None:
    """按 X/Y/Z/W 列提取四元数。"""
    values: list[float] = []
    for axis in ("X", "Y", "Z", "W"):
        value = _try_float(_cell(row, cols[axis]))
        if value is None:
            return None
        values.append(value)
    return np.asarray(values, dtype=np.float64)


def _default_edges(point_count: int) -> list[list[int]]:
    """为模型 JSON 生成默认可视化连线。"""
    if point_count == 8:
        return [
            [0, 1], [1, 2], [2, 3], [3, 0],
            [4, 5], [5, 6], [6, 7], [7, 4],
            [0, 4], [1, 5], [2, 6], [3, 7],
        ]
    return [[idx, idx + 1] for idx in range(point_count - 1)]


def main() -> None:
    """把 marker 世界坐标转换到刚体局部坐标，并输出自定义模型 JSON。"""
    args = parse_args()
    csv_path = Path(args.csv_path).resolve()
    out_path = Path(args.out).resolve()
    report_path = Path(args.report_out).resolve()

    marker_ids = list(args.marker_ids)
    if args.point_names is not None and len(args.point_names) != len(marker_ids):
        raise ValueError("--point-names must have the same number of values as --marker-ids.")
    point_names = list(args.point_names) if args.point_names is not None else [f"marker_{marker_id}" for marker_id in marker_ids]

    layout = _load_fzmotion_layout(csv_path, args.rigid_body)

    missing_markers = [marker_id for marker_id in marker_ids if marker_id not in layout.marker_position_cols or not {"X", "Y", "Z"}.issubset(layout.marker_position_cols[marker_id])]
    if missing_markers:
        available = sorted({name for name in layout.marker_position_cols if name.isdigit()})
        raise ValueError(f"Missing markers in CSV: {missing_markers}. Available marker ids: {available}")

    local_samples: dict[str, list[np.ndarray]] = {marker_id: [] for marker_id in marker_ids}
    used_frames = 0

    for row in layout.data_rows:
        quaternion = _extract_quaternion(row, layout.rigid_rotation_cols)
        translation_mm = _extract_vector(row, layout.rigid_position_cols)
        if quaternion is None or translation_mm is None:
            continue

        rotation = quaternion_to_matrix(quaternion)
        translation_m = translation_mm * layout.unit_scale_to_m

        # 只有刚体和全部目标 marker 同帧有效时，才把这一帧纳入平均。
        frame_ok = True
        world_markers_m: dict[str, np.ndarray] = {}
        for marker_id in marker_ids:
            marker_world_mm = _extract_vector(row, layout.marker_position_cols[marker_id])
            if marker_world_mm is None:
                frame_ok = False
                break
            world_markers_m[marker_id] = marker_world_mm * layout.unit_scale_to_m

        if not frame_ok:
            continue

        rigid_rotation_inv = rotation.T
        for marker_id in marker_ids:
            # p_local = R_world_rigid^T * (p_world_marker - t_world_rigid)
            p_world = world_markers_m[marker_id]
            p_local = rigid_rotation_inv @ (p_world - translation_m)
            local_samples[marker_id].append(p_local)
        used_frames += 1

    if used_frames == 0:
        raise RuntimeError("No valid frames contained both the rigid body pose and all requested markers.")

    points_json: list[dict[str, object]] = []
    stats_json: list[dict[str, object]] = []
    for marker_id, point_name in zip(marker_ids, point_names):
        samples = np.asarray(local_samples[marker_id], dtype=np.float64)
        # 多帧平均可以减小单帧 marker 抖动对模型点的影响。
        mean_xyz = samples.mean(axis=0)
        std_xyz = samples.std(axis=0)
        points_json.append({
            "name": point_name,
            "xyz_m": [float(v) for v in mean_xyz.tolist()],
            "source_marker_id": str(marker_id),
        })
        stats_json.append({
            "name": point_name,
            "source_marker_id": str(marker_id),
            "num_samples": int(samples.shape[0]),
            "mean_xyz_m": [float(v) for v in mean_xyz.tolist()],
            "std_xyz_m": [float(v) for v in std_xyz.tolist()],
        })

    model_payload = {
        "frame": args.rigid_body,
        "description": "Custom car keypoints estimated from FzMotion marker world coordinates and transformed into the rigid body local frame.",
        "points": points_json,
        "edges": _default_edges(len(points_json)),
    }
    report_payload = {
        "csv_path": str(csv_path),
        "rigid_body": args.rigid_body,
        "used_frames": used_frames,
        "point_stats": stats_json,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(model_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "out": str(out_path),
        "report": str(report_path),
        "used_frames": used_frames,
        "markers": marker_ids,
        "point_names": point_names,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()



