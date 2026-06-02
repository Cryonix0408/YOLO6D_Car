"""把旧刚体局部模型点迁移到新刚体坐标系。"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
# 支持直接运行脚本，不要求先安装项目包。
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.config import load_config
from yolo6d_car.transforms import matrix_to_quaternion, quaternion_to_matrix


@dataclass(slots=True)
class FzCsvLayout:
    """缓存一个 FzMotion CSV 中刚体和 marker 位置列的布局。"""

    unit_scale_to_m: float
    rigid_rotation_cols: dict[str, int]
    rigid_position_cols: dict[str, int]
    marker_position_cols: dict[str, dict[str, int]]
    data_rows: list[list[str]]


def parse_args() -> argparse.Namespace:
    """定义刚体重建后坐标系迁移所需的新旧 CSV 和输出路径。"""
    parser = argparse.ArgumentParser(description="Migrate rebuilt rigid-body coordinate frames using old/new FzMotion CSVs.")
    parser.add_argument("--old-csv", required=True)
    parser.add_argument("--new-csv", required=True)
    parser.add_argument("--rigid-body", required=True)
    parser.add_argument("--report-out", default=None)
    parser.add_argument("--project-config", default=None, help="Optional project config to migrate camera_rigid_to_optical from.")
    parser.add_argument("--out-camera-json", default=None)
    parser.add_argument("--old-model-json", default=None)
    parser.add_argument("--out-model-json", default=None)
    return parser.parse_args()


def _normalize_row(row: list[str]) -> list[str]:
    """清理 CSV 行中每个单元格两侧空白。"""
    return [cell.strip() for cell in row]


def _cell(row: list[str], index: int) -> str:
    """安全读取 CSV 单元格，避免行长度不一致时抛 IndexError。"""
    if 0 <= index < len(row):
        return row[index].strip()
    return ""


def _length_unit_scale_to_m(length_units: str) -> float:
    """把 FzMotion 长度单位转换成米。"""
    units = length_units.strip().lower()
    if units in {"m", "meter", "meters"}:
        return 1.0
    if units in {"cm", "centimeter", "centimeters"}:
        return 0.01
    if units in {"mm", "millimeter", "millimeters"}:
        return 0.001
    raise ValueError(f"Unsupported FzMotion length unit: {length_units}")


def _try_float(text: str) -> float | None:
    """将文本转 float，空值和非法值返回 None。"""
    text = text.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _extract_vector(row: list[str], cols: dict[str, int], axes: tuple[str, ...]) -> np.ndarray | None:
    """按给定轴顺序从 CSV 行提取向量。"""
    values: list[float] = []
    for axis in axes:
        value = _try_float(_cell(row, cols[axis]))
        if value is None:
            return None
        values.append(value)
    return np.asarray(values, dtype=np.float64)


def _load_fzmotion_layout(csv_path: Path, rigid_body: str) -> FzCsvLayout:
    """解析 FzMotion 表头，定位指定刚体和刚体 marker 的列。"""
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = [row for row in csv.reader(handle) if any(cell.strip() for cell in row)]

    if not rows or _normalize_row(rows[0])[0] != "DataName":
        raise ValueError(f"Expected an FzMotion CSV: {csv_path}")

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

    prefix = f"{rigid_body}Marker"

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

        if entity_type == "RigidBodyMarker" and entity_name.startswith(prefix):
            if semantic == "Position" and axis in {"X", "Y", "Z"}:
                marker_name = entity_name
                marker_id = marker_name[len(prefix):]
                # 同一 marker 可能以 Rigid0Marker001、001、1 等形式被引用。
                aliases = {marker_name, marker_id, marker_id.lstrip("0") or "0"}
                for alias in aliases:
                    marker_position_cols.setdefault(alias, {})[axis] = col

    if not {"X", "Y", "Z", "W"}.issubset(rigid_rotation_cols):
        raise ValueError(f"Rigid body {rigid_body} missing rotation columns in {csv_path}")
    if not {"X", "Y", "Z"}.issubset(rigid_position_cols):
        raise ValueError(f"Rigid body {rigid_body} missing position columns in {csv_path}")

    return FzCsvLayout(
        unit_scale_to_m=unit_scale,
        rigid_rotation_cols=rigid_rotation_cols,
        rigid_position_cols=rigid_position_cols,
        marker_position_cols=marker_position_cols,
        data_rows=rows[6:],
    )


def _extract_local_markers(csv_path: Path, rigid_body: str) -> dict[str, np.ndarray]:
    """把 CSV 中的刚体 marker 世界坐标转换为该刚体局部坐标并多帧平均。"""
    layout = _load_fzmotion_layout(csv_path, rigid_body)
    marker_ids = sorted(
        alias for alias, cols in layout.marker_position_cols.items()
        if alias.isdigit() and {"X", "Y", "Z"}.issubset(cols)
    )
    local_samples: dict[str, list[np.ndarray]] = {marker_id: [] for marker_id in marker_ids}

    for row in layout.data_rows:
        quat = _extract_vector(row, layout.rigid_rotation_cols, ("X", "Y", "Z", "W"))
        trans = _extract_vector(row, layout.rigid_position_cols, ("X", "Y", "Z"))
        if quat is None or trans is None:
            continue
        rotation = quaternion_to_matrix(quat)
        translation_m = trans * layout.unit_scale_to_m
        rot_inv = rotation.T

        for marker_id in marker_ids:
            vec = _extract_vector(row, layout.marker_position_cols[marker_id], ("X", "Y", "Z"))
            if vec is None:
                continue
            p_world = vec * layout.unit_scale_to_m
            # p_local = R_world_rigid^T * (p_world_marker - t_world_rigid)
            p_local = rot_inv @ (p_world - translation_m)
            local_samples[marker_id].append(p_local)

    result: dict[str, np.ndarray] = {}
    for marker_id, samples in local_samples.items():
        if len(samples) >= 10:
            result[marker_id] = np.mean(np.asarray(samples, dtype=np.float64), axis=0)
    if len(result) < 3:
        raise RuntimeError(f"Too few rigid marker samples found for {rigid_body} in {csv_path}: {sorted(result.keys())}")
    return result


def _signature(points: np.ndarray, index: int, k: int) -> np.ndarray:
    """用到其他点的最近距离集合描述一个 marker 的几何签名。"""
    dists = np.linalg.norm(points - points[index], axis=1)
    dists = np.delete(dists, index)
    dists.sort()
    return dists[:k]


def _best_assignment(cost: np.ndarray) -> list[int]:
    """在 marker 几何签名代价矩阵中寻找总代价最小的一一匹配。"""
    m, n = cost.shape
    order = sorted(range(m), key=lambda i: float(np.min(cost[i])))
    best_cost = math.inf
    best_assignment: list[int] | None = None

    def dfs(depth: int, used: set[int], assignment: dict[int, int], total: float) -> None:
        """小规模 marker 匹配的深度优先搜索。"""
        nonlocal best_cost, best_assignment
        if total >= best_cost:
            return
        if depth == m:
            best_cost = total
            best_assignment = [assignment[i] for i in range(m)]
            return
        i = order[depth]
        candidates = sorted((j for j in range(n) if j not in used), key=lambda j: float(cost[i, j]))
        for j in candidates:
            assignment[i] = j
            used.add(j)
            dfs(depth + 1, used, assignment, total + float(cost[i, j]))
            used.remove(j)
            del assignment[i]

    dfs(0, set(), {}, 0.0)
    if best_assignment is None:
        raise RuntimeError("Failed to infer marker assignment.")
    return best_assignment


def _kabsch(src: np.ndarray, dst: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Kabsch 刚体配准：求 R,t 使 src 尽量对齐 dst。"""
    src_cent = src.mean(axis=0)
    dst_cent = dst.mean(axis=0)
    src_centered = src - src_cent
    dst_centered = dst - dst_cent
    h = src_centered.T @ dst_centered
    u, _, vt = np.linalg.svd(h)
    rotation = vt.T @ u.T
    if np.linalg.det(rotation) < 0:
        vt[-1, :] *= -1.0
        rotation = vt.T @ u.T
    translation = dst_cent - rotation @ src_cent
    transformed = (rotation @ src.T).T + translation
    residuals = transformed - dst
    rms = float(np.sqrt(np.mean(np.sum(residuals * residuals, axis=1))))
    return rotation, translation, rms


def _infer_transform(old_markers: dict[str, np.ndarray], new_markers: dict[str, np.ndarray]) -> dict[str, object]:
    """根据新旧刚体 marker 的局部几何关系推断 T_new_from_old。"""
    old_ids = sorted(old_markers.keys())
    new_ids = sorted(new_markers.keys())
    old_pts = np.asarray([old_markers[mid] for mid in old_ids], dtype=np.float64)
    new_pts = np.asarray([new_markers[mid] for mid in new_ids], dtype=np.float64)

    k = min(len(old_ids), len(new_ids)) - 1
    if k <= 0:
        raise ValueError("Need at least two markers to infer a rigid transform.")

    cost = np.zeros((len(old_ids), len(new_ids)), dtype=np.float64)
    for i in range(len(old_ids)):
        sig_old = _signature(old_pts, i, k)
        for j in range(len(new_ids)):
            sig_new = _signature(new_pts, j, k)
            cost[i, j] = float(np.mean(np.abs(sig_old - sig_new)))

    assignment = _best_assignment(cost)
    matched_new_pts = np.asarray([new_pts[j] for j in assignment], dtype=np.float64)
    # 用已匹配点对拟合旧局部坐标到新局部坐标的刚体变换。
    rotation, translation, rms = _kabsch(old_pts, matched_new_pts)

    mapping = []
    for i in range(len(old_ids)):
        transformed = rotation @ old_pts[i] + translation
        mapping.append(
            {
                "old_marker_id": old_ids[i],
                "new_marker_id": new_ids[assignment[i]],
                "signature_cost_m": float(cost[i, assignment[i]]),
                "old_local_xyz_m": [float(v) for v in old_pts[i].tolist()],
                "new_local_xyz_m": [float(v) for v in matched_new_pts[i].tolist()],
                "aligned_new_minus_transformed_old_m": [float(v) for v in (matched_new_pts[i] - transformed).tolist()],
            }
        )

    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = rotation
    matrix[:3, 3] = translation
    return {
        "old_marker_ids": old_ids,
        "new_marker_ids": new_ids,
        "matched_pairs": mapping,
        "rms_alignment_error_m": rms,
        "translation_m": [float(v) for v in translation.tolist()],
        "quaternion_xyzw": [float(v) for v in matrix_to_quaternion(rotation).tolist()],
        "matrix": matrix.tolist(),
    }


def _load_json(path: Path) -> dict:
    """读取 UTF-8/带 BOM 的 JSON。"""
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: dict) -> None:
    """确保父目录存在后写 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _migrate_camera_pose(project_config_path: Path, rotation: np.ndarray, translation: np.ndarray) -> dict:
    """把旧相机刚体外参迁移到新刚体坐标系下。"""
    config = load_config(project_config_path)
    pose = config.mocap.camera_rigid_to_optical
    if pose is None:
        raise ValueError("Config does not contain mocap.T_camera_rigid_to_optical")
    migrated = np.eye(4, dtype=np.float64)
    migrated[:3, :3] = rotation @ pose.rotation
    migrated[:3, 3] = rotation @ pose.translation_m + translation
    return {
        "translation_m": [float(v) for v in migrated[:3, 3].tolist()],
        "quaternion_xyzw": [float(v) for v in matrix_to_quaternion(migrated[:3, :3]).tolist()],
        "matrix": migrated.tolist(),
    }


def _migrate_model(old_model_path: Path, rotation: np.ndarray, translation: np.ndarray) -> dict:
    """把旧模型点坐标迁移到新刚体局部坐标系。"""
    payload = _load_json(old_model_path)
    points = payload.get("points", [])
    migrated_points = []
    for point in points:
        xyz = np.asarray(point["xyz_m"], dtype=np.float64)
        xyz_new = rotation @ xyz + translation
        migrated_point = dict(point)
        migrated_point["xyz_m"] = [float(v) for v in xyz_new.tolist()]
        migrated_points.append(migrated_point)
    payload["points"] = migrated_points
    payload["description"] = f"Migrated from {old_model_path.name} into rebuilt rigid frame."
    return payload


def main() -> None:
    """读取新旧刚体 CSV，推断迁移变换，并按需迁移相机外参和模型点。"""
    args = parse_args()
    old_csv = Path(args.old_csv).resolve()
    new_csv = Path(args.new_csv).resolve()
    report_out = Path(args.report_out).resolve() if args.report_out else ROOT / "outputs" / "calibration" / f"{args.rigid_body}_migration_report.json"

    old_markers = _extract_local_markers(old_csv, args.rigid_body)
    new_markers = _extract_local_markers(new_csv, args.rigid_body)
    report = {
        "rigid_body": args.rigid_body,
        "old_csv": str(old_csv),
        "new_csv": str(new_csv),
        "num_old_markers": len(old_markers),
        "num_new_markers": len(new_markers),
    }
    result = _infer_transform(old_markers, new_markers)
    report["transform_new_from_old"] = result

    rotation = np.asarray(result["matrix"], dtype=np.float64)[:3, :3]
    translation = np.asarray(result["matrix"], dtype=np.float64)[:3, 3]

    if args.project_config and args.out_camera_json:
        camera_payload = _migrate_camera_pose(Path(args.project_config).resolve(), rotation, translation)
        _write_json(Path(args.out_camera_json).resolve(), camera_payload)
        report["migrated_camera_pose_json"] = str(Path(args.out_camera_json).resolve())

    if args.old_model_json and args.out_model_json:
        model_payload = _migrate_model(Path(args.old_model_json).resolve(), rotation, translation)
        _write_json(Path(args.out_model_json).resolve(), model_payload)
        report["migrated_model_json"] = str(Path(args.out_model_json).resolve())

    _write_json(report_out, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

