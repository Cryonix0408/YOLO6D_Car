"""通过 Mocap 投影与 ArUco 视觉检测对比，验证相机刚体外参质量。"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for search_path in (SRC, SCRIPTS):
    if str(search_path) not in sys.path:
        sys.path.insert(0, str(search_path))

from solve_camera_rigid_to_optical import (  # noqa: E402
    _parse_fzmotion_start_time,
    _resolve_sample_timestamp_s,
    detect_board_pose,
    load_intrinsics,
    load_sample_rows,
)
from yolo6d_car.config import load_config  # noqa: E402
from yolo6d_car.mocap.csv_provider import CSVRigidBodyProvider  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify camera rigid extrinsic by board reprojection.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--samples-dir", required=True)
    parser.add_argument("--csv-path", required=True)
    parser.add_argument("--intrinsics-path", required=True)
    parser.add_argument("--calibration-json", required=True)
    parser.add_argument("--board-rigid-body", required=True)
    parser.add_argument("--markers-x", type=int, required=True)
    parser.add_argument("--markers-y", type=int, required=True)
    parser.add_argument("--marker-length-mm", type=float, required=True)
    parser.add_argument("--marker-separation-mm", type=float, required=True)
    parser.add_argument("--dictionary", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--save-count", type=int, default=30)
    return parser.parse_args()


def load_transform(payload: dict, key: str) -> np.ndarray:
    return np.asarray(payload[key]["matrix"], dtype=np.float64)


def create_board(args: argparse.Namespace, dictionary):
    marker_length_m = args.marker_length_mm / 1000.0
    separation_m = args.marker_separation_mm / 1000.0
    if hasattr(cv2.aruco, "GridBoard_create"):
        return cv2.aruco.GridBoard_create(
            args.markers_x,
            args.markers_y,
            marker_length_m,
            separation_m,
            dictionary,
        )
    return cv2.aruco.GridBoard(
        (args.markers_x, args.markers_y),
        marker_length_m,
        separation_m,
        dictionary,
    )


def board_outline_points(args: argparse.Namespace) -> np.ndarray:
    width_m = (
        args.markers_x * args.marker_length_mm
        + (args.markers_x - 1) * args.marker_separation_mm
    ) / 1000.0
    height_m = (
        args.markers_y * args.marker_length_mm
        + (args.markers_y - 1) * args.marker_separation_mm
    ) / 1000.0
    return np.asarray(
        [[0.0, 0.0, 0.0], [width_m, 0.0, 0.0], [width_m, height_m, 0.0], [0.0, height_m, 0.0]],
        dtype=np.float64,
    )


def project_points(points_xyz: np.ndarray, camera_board: np.ndarray, intrinsics) -> np.ndarray:
    rvec = Rotation.from_matrix(camera_board[:3, :3]).as_rotvec()
    projected, _ = cv2.projectPoints(
        points_xyz,
        rvec,
        camera_board[:3, 3],
        intrinsics.camera_matrix(),
        intrinsics.dist_coeffs,
    )
    return projected.reshape(-1, 2)


def pose_error(reference: np.ndarray, candidate: np.ndarray) -> tuple[float, float]:
    delta = np.linalg.inv(reference) @ candidate
    translation_error_m = float(np.linalg.norm(delta[:3, 3]))
    rotation_error_deg = float(np.rad2deg(np.linalg.norm(Rotation.from_matrix(delta[:3, :3]).as_rotvec())))
    return translation_error_m, rotation_error_deg


def draw_polygon(image: np.ndarray, points: np.ndarray, color: tuple[int, int, int], label: str) -> None:
    rounded = np.rint(points).astype(np.int32)
    cv2.polylines(image, [rounded.reshape(-1, 1, 2)], True, color, 3, cv2.LINE_AA)
    cv2.putText(image, label, tuple(rounded[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2, cv2.LINE_AA)


def main() -> None:
    args = parse_args()
    samples_dir = Path(args.samples_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    overlays_dir = output_dir / "overlays"
    overlays_dir.mkdir(parents=True, exist_ok=True)

    config = load_config(args.config)
    provider = CSVRigidBodyProvider(args.csv_path)
    mocap_start_dt = _parse_fzmotion_start_time(provider.metadata.get("StartTime", ""))
    intrinsics = load_intrinsics(Path(args.intrinsics_path).resolve())
    calibration = json.loads(Path(args.calibration_json).read_text(encoding="utf-8-sig"))
    camera_rigid_to_optical = load_transform(calibration, "T_camera_rigid_to_optical")
    board_rigid_to_visual = load_transform(calibration, "T_board_rigid_to_board_visual")

    dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, args.dictionary))
    board = create_board(args, dictionary)
    outline_xyz = board_outline_points(args)
    rows, sample_source = load_sample_rows(samples_dir)

    valid_results: list[dict[str, float | int | str]] = []
    valid_payloads: list[tuple[Path, np.ndarray, np.ndarray, np.ndarray, dict[str, float | int | str]]] = []
    for row in rows:
        image_path = Path(row["image_path"])
        if not image_path.is_absolute():
            image_path = samples_dir / image_path
        timestamp_s, timestamp_source = _resolve_sample_timestamp_s(row, mocap_start_dt)
        camera_rigid = provider.get_pose(config.mocap.camera_rigid_body, timestamp_s, config.mocap.max_time_diff_s)
        board_rigid = provider.get_pose(args.board_rigid_body, timestamp_s, config.mocap.max_time_diff_s)
        if camera_rigid is None or board_rigid is None:
            continue
        visual_detection = detect_board_pose(image_path, intrinsics, dictionary, board)
        if visual_detection is None:
            continue

        world_camera_optical = camera_rigid.as_matrix() @ camera_rigid_to_optical
        world_board_visual = board_rigid.as_matrix() @ board_rigid_to_visual
        mocap_camera_board = np.linalg.inv(world_camera_optical) @ world_board_visual

        mocap_uv = project_points(outline_xyz, mocap_camera_board, intrinsics)
        visual_uv = project_points(outline_xyz, visual_detection.camera_board_visual, intrinsics)
        corner_error_px = float(np.mean(np.linalg.norm(mocap_uv - visual_uv, axis=1)))
        translation_error_m, rotation_error_deg = pose_error(
            visual_detection.camera_board_visual,
            mocap_camera_board,
        )
        result = {
            "sample_index": int(row["sample_index"]),
            "image_path": str(image_path),
            "timestamp_s": float(timestamp_s),
            "timestamp_source": timestamp_source,
            "marker_count": int(visual_detection.marker_count),
            "mean_corner_error_px": corner_error_px,
            "translation_error_m": translation_error_m,
            "rotation_error_deg": rotation_error_deg,
        }
        valid_results.append(result)
        valid_payloads.append((image_path, mocap_uv, visual_uv, mocap_camera_board, result))

    if not valid_results:
        raise RuntimeError("No valid verification samples. Check timestamps, rigid names, board parameters and images.")

    save_count = min(max(args.save_count, 1), len(valid_payloads))
    save_indices = set(np.linspace(0, len(valid_payloads) - 1, save_count, dtype=int).tolist())
    for index, (image_path, mocap_uv, visual_uv, _, result) in enumerate(valid_payloads):
        if index not in save_indices:
            continue
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            continue
        draw_polygon(image, visual_uv, (0, 255, 0), "Vision ArUco")
        draw_polygon(image, mocap_uv, (255, 255, 0), "Mocap projection")
        text = (
            f"corner={result['mean_corner_error_px']:.1f}px "
            f"trans={result['translation_error_m'] * 1000.0:.1f}mm "
            f"rot={result['rotation_error_deg']:.2f}deg"
        )
        cv2.putText(image, text, (20, image.shape[0] - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 5, cv2.LINE_AA)
        cv2.putText(image, text, (20, image.shape[0] - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 255), 2, cv2.LINE_AA)
        cv2.imwrite(str(overlays_dir / f"verify_{int(result['sample_index']):06d}.png"), image)

    csv_path = output_dir / "verification_samples.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(valid_results[0].keys()))
        writer.writeheader()
        writer.writerows(valid_results)

    def stats(key: str) -> dict[str, float]:
        values = np.asarray([float(row[key]) for row in valid_results], dtype=np.float64)
        return {
            "mean": float(np.mean(values)),
            "median": float(np.median(values)),
            "p90": float(np.percentile(values, 90)),
            "max": float(np.max(values)),
        }

    summary = {
        "num_valid_samples": len(valid_results),
        "sample_source": sample_source,
        "mean_corner_error_px": stats("mean_corner_error_px"),
        "translation_error_m": stats("translation_error_m"),
        "rotation_error_deg": stats("rotation_error_deg"),
        "overlays_dir": str(overlays_dir),
        "samples_csv": str(csv_path),
    }
    summary_path = output_dir / "verification_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
