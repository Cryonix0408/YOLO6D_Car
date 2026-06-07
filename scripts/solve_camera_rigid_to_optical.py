"""利用标定板和 Mocap 求解相机刚体到光学坐标系的外参。"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import yaml
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
# 允许直接从项目目录运行脚本并导入 src/yolo6d_car。
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    import cv2
except ImportError:
    raise RuntimeError('opencv-contrib-python is required.')

if not hasattr(cv2, 'aruco'):
    raise RuntimeError('OpenCV aruco module is missing.')

from yolo6d_car.config import load_config
from yolo6d_car.mocap.csv_provider import CSVRigidBodyProvider
from yolo6d_car.transforms import matrix_to_quaternion
from yolo6d_car.types import CameraIntrinsics


@dataclass(slots=True)
class Observation:
    """一次有效标定样本：同一时刻的 Mocap 位姿和视觉标定板位姿。"""

    sample_index: int
    image_path: Path
    mocap_timestamp_s: float
    world_camera_rigid: np.ndarray
    world_board_rigid: np.ndarray
    camera_board_visual: np.ndarray
    marker_count: int


@dataclass(slots=True)
class BoardDetection:
    """OpenCV ArUco 检出的相机到标定板位姿。"""

    camera_board_visual: np.ndarray
    marker_count: int


def parse_args() -> argparse.Namespace:
    """定义相机刚体到光学坐标系外参求解参数。"""
    parser = argparse.ArgumentParser(description='Calibrate T_camera_rigid_to_optical using ArUco board and mocap.')
    parser.add_argument('--config', required=True)
    parser.add_argument('--samples-dir', required=True)
    parser.add_argument('--board-rigid-body', required=True)
    parser.add_argument('--markers-x', type=int, required=True)
    parser.add_argument('--markers-y', type=int, required=True)
    parser.add_argument('--marker-length-mm', type=float, required=True)
    parser.add_argument('--marker-separation-mm', type=float, required=True)
    parser.add_argument('--dictionary', required=True)
    parser.add_argument('--csv-path', default=None, help='Optional FzMotion CSV path. Overrides mocap.csv_path in config.')
    parser.add_argument('--intrinsics-path', default=None, help='Optional camera intrinsics JSON/YAML path. If omitted, auto-detect from samples-dir or common calibration outputs.')
    parser.add_argument('--timestamp-start-local-time', default=None, help='Optional local capture start time for camera_timestamps.csv, e.g. 2026-06-04T15:08:32.000.')
    parser.add_argument('--camera-init-config', default=None, help='Optional YAML whose mocap.T_camera_rigid_to_optical is used as initialization and soft prior.')
    parser.add_argument('--no-camera-prior', action='store_true', help='Do not use camera extrinsic from config as initialization/prior. Use this after rebuilding the camera rigid body.')
    parser.add_argument('--camera-translation-prior-sigma-m', type=float, default=0.08, help='Soft prior sigma for camera extrinsic translation around the init value.')
    parser.add_argument('--camera-rotation-prior-sigma-deg', type=float, default=12.0, help='Soft prior sigma for camera extrinsic rotation around the init value.')
    parser.add_argument('--out', default=str(ROOT / 'outputs' / 'calibration' / 'camera_rigid_to_optical.json'))
    return parser.parse_args()


def load_intrinsics(path: Path) -> CameraIntrinsics:
    """读取采集时保存的相机内参，兼容旧 JSON、海康 YAML 和 calibration_summary.json。"""
    if not path.exists():
        raise FileNotFoundError(f'Camera intrinsics file not found: {path}')

    if path.suffix.lower() in {'.yaml', '.yml'}:
        data = yaml.safe_load(path.read_text(encoding='utf-8-sig'))
    else:
        data = json.loads(path.read_text(encoding='utf-8-sig'))

    if 'camera_matrix' in data and isinstance(data['camera_matrix'], dict):
        # 新的海康内参 YAML 格式。
        camera_raw = data.get('camera', {})
        matrix_raw = data['camera_matrix']
        distortion_raw = data.get('distortion', {})
        return CameraIntrinsics(
            fx=float(matrix_raw['fx']),
            fy=float(matrix_raw['fy']),
            cx=float(matrix_raw['cx']),
            cy=float(matrix_raw['cy']),
            width=int(camera_raw['width']),
            height=int(camera_raw['height']),
            dist_coeffs=np.asarray(distortion_raw.get('vector', []), dtype=np.float64),
        )

    if 'camera_matrix' in data and isinstance(data['camera_matrix'], list):
        # calibrate_hik_camera.py 生成的 calibration_summary.json 格式。
        matrix = np.asarray(data['camera_matrix'], dtype=np.float64)
        image_size = data['image_size']
        return CameraIntrinsics(
            fx=float(matrix[0, 0]),
            fy=float(matrix[1, 1]),
            cx=float(matrix[0, 2]),
            cy=float(matrix[1, 2]),
            width=int(image_size['width']),
            height=int(image_size['height']),
            dist_coeffs=np.asarray(data.get('distortion_coefficients', []), dtype=np.float64),
        )

    # 旧 D455 intrinsics.json 格式。
    return CameraIntrinsics(
        fx=float(data['fx']),
        fy=float(data['fy']),
        cx=float(data['cx']),
        cy=float(data['cy']),
        width=int(data['width']),
        height=int(data['height']),
        dist_coeffs=np.asarray(data['dist_coeffs'], dtype=np.float64),
    )


def find_intrinsics_path(samples_dir: Path, explicit_path: str | None) -> Path:
    """自动寻找外参求解要用的相机内参文件。"""
    if explicit_path:
        return Path(explicit_path).resolve()

    candidates = [
        samples_dir / 'intrinsics.json',
        samples_dir / 'camera_intrinsics.yaml',
        samples_dir / 'camera_intrinsics.yml',
        ROOT / 'outputs' / 'calibration' / 'hik_6mm' / 'camera_intrinsics_hik_6mm.yaml',
        Path('D:/CaptureData/outputs/calibration/hik_6mm/camera_intrinsics_hik_6mm.yaml'),
        Path('D:/CaptureData/outputs/calibration/hik_6mm/calibration_summary.json'),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    raise FileNotFoundError(
        'No camera intrinsics file found. Pass --intrinsics-path explicitly, '
        'for example D:\\CaptureData\\outputs\\calibration\\hik_6mm\\camera_intrinsics_hik_6mm.yaml'
    )


def detect_board_pose(image_path: Path, intrinsics: CameraIntrinsics, dictionary, board) -> BoardDetection | None:
    """在单张图片中检测 ArUco 标定板，并估计 T_camera_board_visual。"""
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None

    if hasattr(cv2.aruco, 'detectMarkers'):
        corners, ids, _ = cv2.aruco.detectMarkers(img, dictionary)
    else:
        if hasattr(cv2.aruco, 'DetectorParameters'):
            detector_params = cv2.aruco.DetectorParameters()
        else:
            detector_params = cv2.aruco.DetectorParameters_create()
        detector = cv2.aruco.ArucoDetector(dictionary, detector_params)
        corners, ids, _ = detector.detectMarkers(img)

    if ids is None or len(ids) < 4:
        return None

    if hasattr(cv2.aruco, 'estimatePoseBoard'):
        # 新旧 OpenCV aruco API 不完全一致；优先使用高层 board pose 接口。
        retval, rvec, tvec = cv2.aruco.estimatePoseBoard(
            corners,
            ids,
            board,
            intrinsics.camera_matrix(),
            intrinsics.dist_coeffs,
            None,
            None,
        )
        if retval <= 0:
            return None
    else:
        # 兼容没有 estimatePoseBoard 的版本，手动取 3D/2D 点后 solvePnP。
        if hasattr(board, 'matchImagePoints'):
            object_points, image_points = board.matchImagePoints(corners, ids)
        elif hasattr(cv2.aruco, 'getBoardObjectAndImagePoints'):
            object_points, image_points = cv2.aruco.getBoardObjectAndImagePoints(board, corners, ids)
        else:
            raise RuntimeError('Current OpenCV aruco API does not support board pose estimation.')

        object_points = np.asarray(object_points, dtype=np.float64).reshape(-1, 3)
        image_points = np.asarray(image_points, dtype=np.float64).reshape(-1, 2)
        if len(object_points) < 4:
            return None

        ok, rvec, tvec = cv2.solvePnP(
            object_points,
            image_points,
            intrinsics.camera_matrix(),
            intrinsics.dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
        if not ok:
            return None

    rotation, _ = cv2.Rodrigues(rvec)
    transform = np.eye(4, dtype=np.float64)
    transform[:3, :3] = rotation
    transform[:3, 3] = np.asarray(tvec, dtype=np.float64).reshape(3)
    return BoardDetection(camera_board_visual=transform, marker_count=len(ids))


def average_quaternions(quaternions: list[np.ndarray]) -> np.ndarray:
    """对多组四元数求平均，先统一 q/-q 符号。"""
    qs = np.asarray(quaternions, dtype=np.float64)
    if len(qs) == 1:
        return qs[0] / np.linalg.norm(qs[0])
    for idx in range(1, len(qs)):
        if np.dot(qs[0], qs[idx]) < 0.0:
            qs[idx] *= -1.0
    q_mean = qs.mean(axis=0)
    return q_mean / np.linalg.norm(q_mean)


def average_transforms(transforms: list[np.ndarray]) -> np.ndarray:
    """对一组 SE3 变换做简单平均，用作优化初值。"""
    translations = [T[:3, 3] for T in transforms]
    rotations = [matrix_to_quaternion(T[:3, :3]) for T in transforms]
    averaged = np.eye(4, dtype=np.float64)
    averaged[:3, 3] = np.mean(translations, axis=0)
    averaged[:3, :3] = Rotation.from_quat(average_quaternions(rotations)).as_matrix()
    return averaged


def pack_transform(transform: np.ndarray) -> np.ndarray:
    """把 4x4 变换打包为 6 维优化参数：rotvec + translation。"""
    rotvec = Rotation.from_matrix(transform[:3, :3]).as_rotvec()
    translation = transform[:3, 3]
    return np.concatenate([rotvec, translation])


def unpack_transform(params: np.ndarray) -> np.ndarray:
    """把 6 维优化参数还原为 4x4 变换矩阵。"""
    transform = np.eye(4, dtype=np.float64)
    transform[:3, :3] = Rotation.from_rotvec(np.asarray(params[:3], dtype=np.float64)).as_matrix()
    transform[:3, 3] = np.asarray(params[3:6], dtype=np.float64)
    return transform


def transform_delta_vector(reference_transform: np.ndarray, candidate_transform: np.ndarray) -> np.ndarray:
    """计算 candidate 相对 reference 的 6 维小量，用于软先验。"""
    delta = np.linalg.inv(reference_transform) @ candidate_transform
    return pack_transform(delta)


def optimization_residuals(
    params: np.ndarray,
    observations: list[Observation],
    camera_init_transform: np.ndarray | None,
    camera_translation_prior_sigma_m: float | None,
    camera_rotation_prior_sigma_rad: float | None,
) -> np.ndarray:
    """优化残差：让 Mocap 链路和视觉链路预测同一个标定板位姿。"""
    camera_rigid_to_optical = unpack_transform(params[:6])
    board_rigid_to_board_visual = unpack_transform(params[6:12])

    residuals: list[float] = []
    for obs in observations:
        # 左边：world -> camera_rigid -> camera_optical -> board_visual。
        left = obs.world_camera_rigid @ camera_rigid_to_optical @ obs.camera_board_visual
        # 右边：world -> board_rigid -> board_visual。
        right = obs.world_board_rigid @ board_rigid_to_board_visual
        delta = np.linalg.inv(right) @ left
        residuals.extend(delta[:3, 3].tolist())
        residuals.extend(Rotation.from_matrix(delta[:3, :3]).as_rotvec().tolist())

    if (
        camera_init_transform is not None
        and camera_translation_prior_sigma_m is not None
        and camera_rotation_prior_sigma_rad is not None
    ):
        # 先验防止优化从已有外参附近跳到不合理的等价解。
        delta_params = transform_delta_vector(camera_init_transform, camera_rigid_to_optical)
        residuals.extend((delta_params[3:6] / camera_translation_prior_sigma_m).tolist())
        residuals.extend((delta_params[0:3] / camera_rotation_prior_sigma_rad).tolist())

    return np.asarray(residuals, dtype=np.float64)


def transform_to_dict(transform: np.ndarray) -> dict[str, object]:
    """把 4x4 变换转换成 JSON 友好的平移、四元数和矩阵。"""
    return {
        'translation_m': [float(v) for v in transform[:3, 3]],
        'quaternion_xyzw': [float(v) for v in matrix_to_quaternion(transform[:3, :3])],
        'matrix': [[float(v) for v in row] for row in transform.tolist()],
    }


def _parse_fzmotion_start_time(text: str) -> datetime | None:
    """解析 FzMotion CSV 元数据中的 StartTime。"""
    text = (text or '').strip()
    if not text:
        return None
    for fmt in ('%Y.%m.%d %H:%M:%S:%f', '%Y.%m.%d %H:%M:%S'):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None


def _resolve_sample_timestamp_s(row: dict[str, str], mocap_start_dt: datetime | None) -> tuple[float, str]:
    """把 samples.csv 时间字段归一到 Mocap 相对秒时间轴。"""
    saved_local_time = (row.get('saved_local_time') or '').strip()
    if saved_local_time and mocap_start_dt is not None:
        try:
            sample_dt = datetime.fromisoformat(saved_local_time)
            return (sample_dt - mocap_start_dt).total_seconds(), 'saved_local_time'
        except ValueError:
            pass

    saved_unix = (row.get('saved_unix_time_s') or '').strip()
    if saved_unix and mocap_start_dt is not None:
        try:
            sample_dt = datetime.fromtimestamp(float(saved_unix))
            return (sample_dt - mocap_start_dt).total_seconds(), 'saved_unix_time_s'
        except ValueError:
            pass

    return float(row['device_timestamp_s']), 'device_timestamp_s'


def _load_capture_fps(samples_dir: Path) -> float | None:
    """从海康采集 config.yaml 读取目标帧率，用于旧数据补时间戳。"""
    config_path = samples_dir / 'config.yaml'
    if not config_path.exists():
        return None
    data = yaml.safe_load(config_path.read_text(encoding='utf-8-sig')) or {}
    capture = data.get('capture', {})
    camera = data.get('camera', {})
    for raw_value in (capture.get('target_fps'), camera.get('fps')):
        if raw_value is not None:
            return float(raw_value)
    return None


def _resolve_legacy_start_time(samples_dir: Path, explicit_start_time: str | None) -> datetime | None:
    """为没有 saved_local_time 的旧海康采集估计本地采集开始时间。"""
    if explicit_start_time:
        return datetime.fromisoformat(explicit_start_time)

    first_image = samples_dir / 'images' / '000001.png'
    if first_image.exists():
        # Windows 上 st_ctime 是创建时间；这比写入完成时间更接近第一帧采集时间。
        return datetime.fromtimestamp(first_image.stat().st_ctime)

    return None


def load_sample_rows(samples_dir: Path, timestamp_start_local_time: str | None = None) -> tuple[list[dict[str, str]], str]:
    """读取外参样本列表，兼容老 samples.csv 和海康 camera_timestamps.csv。"""
    samples_csv = samples_dir / 'samples.csv'
    if samples_csv.exists():
        with samples_csv.open('r', encoding='utf-8-sig', newline='') as handle:
            return list(csv.DictReader(handle)), 'samples.csv'

    timestamps_csv = samples_dir / 'camera_timestamps.csv'
    if timestamps_csv.exists():
        rows: list[dict[str, str]] = []
        capture_fps = _load_capture_fps(samples_dir)
        legacy_start_dt = _resolve_legacy_start_time(samples_dir, timestamp_start_local_time)
        with timestamps_csv.open('r', encoding='utf-8-sig', newline='') as handle:
            for index, row in enumerate(csv.DictReader(handle)):
                image_path = Path(row['image_path'])
                if image_path.is_absolute():
                    relative_image_path = image_path.relative_to(samples_dir) if image_path.is_relative_to(samples_dir) else image_path
                else:
                    relative_image_path = image_path
                normalized_row = {
                    'sample_index': str(index),
                    'image_path': str(relative_image_path),
                    'device_timestamp_s': row['timestamp'],
                }
                if row.get('saved_local_time'):
                    normalized_row['saved_local_time'] = row['saved_local_time']
                elif legacy_start_dt is not None and capture_fps is not None and capture_fps > 0:
                    # 旧版海康采集没有本地时间。这里按 D455 的 saved_local_time 语义补齐：
                    # 第一张图创建时间作为采集起点，再按固定 fps 推算每一帧时间。
                    inferred_dt = legacy_start_dt.timestamp() + index / capture_fps
                    normalized_row['saved_local_time'] = datetime.fromtimestamp(inferred_dt).isoformat(timespec='milliseconds')
                if row.get('saved_unix_time_s'):
                    normalized_row['saved_unix_time_s'] = row['saved_unix_time_s']
                rows.append(
                    normalized_row
                )
        return rows, 'camera_timestamps.csv'

    raise FileNotFoundError(f'No samples.csv or camera_timestamps.csv found in: {samples_dir}')


def _load_camera_init_transform(base_config, args: argparse.Namespace) -> np.ndarray | None:
    """从可选初始化配置或当前配置读取相机刚体外参初值。"""
    if args.no_camera_prior:
        return None

    if args.camera_init_config:
        init_config = load_config(args.camera_init_config)
        if init_config.mocap.camera_rigid_to_optical is None:
            raise RuntimeError('camera-init-config does not contain mocap.T_camera_rigid_to_optical')
        return init_config.mocap.camera_rigid_to_optical.as_matrix()

    if base_config.mocap.camera_rigid_to_optical is not None:
        return base_config.mocap.camera_rigid_to_optical.as_matrix()

    return None


def _estimate_board_init_transform(observations: list[Observation], camera_init_transform: np.ndarray | None) -> np.ndarray:
    """利用已有相机初值反推 board_rigid 到 board_visual 的初始变换。"""
    if camera_init_transform is None:
        return np.eye(4, dtype=np.float64)
    estimates: list[np.ndarray] = []
    for obs in observations:
        estimate = np.linalg.inv(obs.world_board_rigid) @ obs.world_camera_rigid @ camera_init_transform @ obs.camera_board_visual
        estimates.append(estimate)
    if not estimates:
        return np.eye(4, dtype=np.float64)
    return average_transforms(estimates)


def main() -> None:
    """构建标定观测，联合优化相机外参和标定板刚体外参。"""
    args = parse_args()
    config = load_config(args.config)
    csv_path = Path(args.csv_path).resolve() if args.csv_path else config.mocap.csv_path
    if csv_path is None:
        raise RuntimeError('Mocap csv_path is not configured. Pass --csv-path or set mocap.csv_path in config.')
    provider = CSVRigidBodyProvider(csv_path)
    mocap_start_dt = _parse_fzmotion_start_time(provider.metadata.get('StartTime', ''))
    samples_dir = Path(args.samples_dir).resolve()
    intrinsics_path = find_intrinsics_path(samples_dir, args.intrinsics_path)
    intrinsics = load_intrinsics(intrinsics_path)

    dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, args.dictionary))
    if hasattr(cv2.aruco, 'GridBoard_create'):
        board = cv2.aruco.GridBoard_create(
            args.markers_x,
            args.markers_y,
            args.marker_length_mm / 1000.0,
            args.marker_separation_mm / 1000.0,
            dictionary,
        )
    else:
        board = cv2.aruco.GridBoard(
            (args.markers_x, args.markers_y),
            args.marker_length_mm / 1000.0,
            args.marker_separation_mm / 1000.0,
            dictionary,
        )

    observations: list[Observation] = []
    sample_rows, sample_source = load_sample_rows(samples_dir, args.timestamp_start_local_time)
    for row in sample_rows:
        image_path = Path(row['image_path'])
        if not image_path.is_absolute():
            image_path = samples_dir / image_path
        timestamp, _ = _resolve_sample_timestamp_s(row, mocap_start_dt)
        # 同一时刻必须同时拿到相机刚体、标定板刚体和视觉标定板检测。
        world_camera_rigid = provider.get_pose(config.mocap.camera_rigid_body, timestamp, config.mocap.max_time_diff_s)
        world_board_rigid = provider.get_pose(args.board_rigid_body, timestamp, config.mocap.max_time_diff_s)
        if world_camera_rigid is None or world_board_rigid is None:
            continue

        detection = detect_board_pose(image_path, intrinsics, dictionary, board)
        if detection is None:
            continue

        observations.append(
            Observation(
                sample_index=int(row['sample_index']),
                image_path=image_path,
                mocap_timestamp_s=timestamp,
                world_camera_rigid=world_camera_rigid.as_matrix(),
                world_board_rigid=world_board_rigid.as_matrix(),
                camera_board_visual=detection.camera_board_visual,
                marker_count=detection.marker_count,
            )
        )

    if not observations:
        raise RuntimeError('No valid observations were built. Check images, CSV, rigid body names, and board parameters.')

    camera_prior_transform = _load_camera_init_transform(config, args)
    board_init_transform = _estimate_board_init_transform(observations, camera_prior_transform)

    camera_init_transform = camera_prior_transform
    if camera_init_transform is None:
        camera_init_transform = np.eye(4, dtype=np.float64)

    x0 = np.concatenate([pack_transform(camera_init_transform), pack_transform(board_init_transform)])

    # 参数前 6 维是 T_camera_rigid_to_optical，后 6 维是 T_board_rigid_to_board_visual。
    result = least_squares(
        optimization_residuals,
        x0,
        args=(
            observations,
            camera_prior_transform,
            float(args.camera_translation_prior_sigma_m),
            np.deg2rad(float(args.camera_rotation_prior_sigma_deg)),
        ),
        loss='soft_l1',
    )

    camera_rigid_to_optical = unpack_transform(result.x[:6])
    board_rigid_to_board_visual = unpack_transform(result.x[6:12])

    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'T_camera_rigid_to_optical': transform_to_dict(camera_rigid_to_optical),
        'T_board_rigid_to_board_visual': transform_to_dict(board_rigid_to_board_visual),
        'num_used_samples': len(observations),
        'optimization_success': bool(result.success),
        'optimization_message': str(result.message),
        'metadata': {
            'config': str(Path(args.config).resolve()),
            'camera_init_config': None if args.camera_init_config is None else str(Path(args.camera_init_config).resolve()),
            'camera_prior_enabled': camera_prior_transform is not None,
            'samples_dir': str(samples_dir),
            'sample_source': sample_source,
            'intrinsics_path': str(intrinsics_path),
            'csv_path': str(Path(csv_path).resolve()),
            'camera_rigid_body': str(config.mocap.camera_rigid_body),
            'board_rigid_body': str(args.board_rigid_body),
            'markers_x': int(args.markers_x),
            'markers_y': int(args.markers_y),
            'marker_length_mm': float(args.marker_length_mm),
            'marker_separation_mm': float(args.marker_separation_mm),
            'dictionary': str(args.dictionary),
            'mocap_start_time': provider.metadata.get('StartTime', ''),
            'timestamp_source': 'saved_local_time if available else fallback',
            'camera_translation_prior_sigma_m': float(args.camera_translation_prior_sigma_m),
            'camera_rotation_prior_sigma_deg': float(args.camera_rotation_prior_sigma_deg),
        },
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    print('T_camera_rigid_to_optical =')
    print(camera_rigid_to_optical)
    print()
    print('T_board_rigid_to_board_visual =')
    print(board_rigid_to_board_visual)
    print()
    print(f'num_used_samples = {len(observations)}')
    print(f'optimization_success = {result.success}')
    print(f'json_saved_to = {output_path}')


if __name__ == '__main__':
    main()

