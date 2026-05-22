"""根据多组静态样本估计世界坐标系下的相机光学位姿。"""

from pathlib import Path
import sys

# ------------------------------------------------------------
# 将项目根目录下的 src 路径加入 Python 搜索路径
# 这样就可以导入 yolo6d_car 包中的模块
# ------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import argparse
import json
import numpy as np

# ------------------------------------------------------------
# 导入位姿变换相关函数
# compose_poses: 位姿连乘
# invert_pose: 位姿求逆
# matrix_to_quaternion: 旋转矩阵转四元数
# pose_from_quaternion_translation: 由平移+四元数构造位姿对象
# ------------------------------------------------------------
from yolo6d_car.transforms import (
    compose_poses,
    invert_pose,
    matrix_to_quaternion,
    pose_from_quaternion_translation,
)


def load_pose(raw_pose: dict, parent_frame: str, child_frame: str):
    """
    将原始字典格式的位姿数据，转换为项目内部统一使用的 pose 对象。

    参数:
        raw_pose: 一个字典，至少包含：
            - translation_m: 平移，单位米，例如 [x, y, z]
            - quaternion_xyzw: 四元数，例如 [qx, qy, qz, qw]
        parent_frame: 父坐标系名称
        child_frame: 子坐标系名称

    返回:
        pose 对象
    """
    return pose_from_quaternion_translation(
        parent_frame=parent_frame,
        child_frame=child_frame,
        translation_m=np.asarray(raw_pose["translation_m"], dtype=np.float64),
        quaternion_xyzw=np.asarray(raw_pose["quaternion_xyzw"], dtype=np.float64),
    )


def average_quaternions(quaternions_xyzw: np.ndarray) -> np.ndarray:
    """
    对多组四元数做平均。

    注意：
    四元数 q 和 -q 表示同一个旋转，
    所以平均前必须先做“符号对齐”，否则会互相抵消。

    参数:
        quaternions_xyzw: shape = (N, 4) 的四元数数组

    返回:
        平均后的单位四元数，shape = (4,)
    """
    if quaternions_xyzw.ndim != 2 or quaternions_xyzw.shape[1] != 4:
        raise ValueError("quaternions_xyzw must have shape (N, 4)")

    # 复制一份，避免修改原始输入
    aligned = quaternions_xyzw.copy()

    # 以第一个四元数为参考，对后续四元数做符号统一
    reference = aligned[0]
    for index in range(1, aligned.shape[0]):
        # 如果点积小于 0，说明方向相反，需要乘以 -1 做对齐
        if np.dot(reference, aligned[index]) < 0.0:
            aligned[index] *= -1.0

    # 对齐后按元素求平均
    mean_quaternion = aligned.mean(axis=0)

    # 再归一化，确保仍然是单位四元数
    norm = np.linalg.norm(mean_quaternion)
    if norm == 0.0:
        raise ValueError("Quaternion average is undefined because the mean norm is zero.")
    return mean_quaternion / norm


def compute_world_camera_optical(samples: list[dict]) -> dict:
    """
    根据多组标定样本，计算相机光学坐标系在动捕世界坐标系下的平均位姿。

    每个样本都应该包含两部分：
        1. world_board: 标定板在动捕世界坐标系下的位姿
           即 T_world_board
        2. camera_board: 标定板在相机光学坐标系下的位姿
           即 T_camera_board

    对于每个样本，根据公式：
        T_world_camera = T_world_board * inverse(T_camera_board)

    计算出一个相机在世界中的位姿，然后对多组样本做平均。

    参数:
        samples: 样本列表，每个元素是一个字典

    返回:
        一个字典，包含：
        - translation_m: 平均平移
        - quaternion_xyzw: 平均四元数
        - num_samples: 样本数量
        - translation_std_m: 平移标准差
    """
    if not samples:
        raise ValueError("At least one calibration sample is required.")

    # 用于存储每个样本算出的相机平移和旋转
    translations = []
    quaternions = []

    for sample in samples:
        # --------------------------------------------------------
        # 读取“标定板在世界坐标系下的位姿”
        # 即 T_world_board
        # --------------------------------------------------------
        world_board = load_pose(
            sample["world_board"],
            parent_frame="mocap_world",
            child_frame="calibration_board",
        )

        # --------------------------------------------------------
        # 读取“标定板在相机光学坐标系下的位姿”
        # 即 T_camera_board
        # --------------------------------------------------------
        camera_board = load_pose(
            sample["camera_board"],
            parent_frame="camera_optical",
            child_frame="calibration_board",
        )

        # --------------------------------------------------------
        # 根据位姿关系计算：
        # T_world_camera = T_world_board * inverse(T_camera_board)
        #
        # 解释：
        # 已知：
        #   世界 -> 标定板
        #   相机 -> 标定板
        # 想求：
        #   世界 -> 相机
        # --------------------------------------------------------
        world_camera = compose_poses(world_board, invert_pose(camera_board))

        # 保存该样本下相机的平移
        translations.append(world_camera.translation_m)

        # 将旋转矩阵转为四元数后保存
        quaternions.append(matrix_to_quaternion(world_camera.rotation))

    # 转成 numpy 数组便于后续求均值
    translations_np = np.asarray(translations, dtype=np.float64)
    quaternions_np = np.asarray(quaternions, dtype=np.float64)

    # 平移直接按列取均值
    mean_translation = translations_np.mean(axis=0)

    # 旋转用四元数平均
    mean_quaternion = average_quaternions(quaternions_np)

    # 返回结果
    return {
        "translation_m": mean_translation.tolist(),
        "quaternion_xyzw": mean_quaternion.tolist(),
        "num_samples": len(samples),
        "translation_std_m": translations_np.std(axis=0).tolist(),
    }


def parse_args() -> argparse.Namespace:
    """
    解析命令行参数。
    """
    parser = argparse.ArgumentParser(
        description="Compute T_world_camera_optical from multiple calibration samples."
    )
    parser.add_argument(
        "--samples",
        required=True,
        help="Path to a JSON file containing calibration samples."
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional path to write the resulting JSON."
    )
    return parser.parse_args()


def main() -> None:
    """
    主函数：
    1. 读取样本 JSON
    2. 计算相机在世界中的平均位姿
    3. 打印结果
    4. 如果指定输出路径，则保存结果到 JSON 文件
    """
    args = parse_args()

    # 读取输入 JSON 文件
    with Path(args.samples).open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)

    # 调用主计算函数
    result = compute_world_camera_optical(payload["samples"])

    # 转为格式化 JSON 字符串
    text = json.dumps(result, indent=2, ensure_ascii=False)

    # 打印到终端
    print(text)

    # 如果指定了输出文件，则写入磁盘
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8-sig")


if __name__ == "__main__":
    main()
