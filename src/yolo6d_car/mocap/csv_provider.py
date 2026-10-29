"""FzMotion / 通用 CSV 刚体位姿读取与按时间查询。"""

from __future__ import annotations

# 二分查找，用来快速按时间戳找最近样本
import bisect

# 读 CSV 文件
import csv

# dataclass 用来简化类定义
from dataclasses import dataclass

# 路径处理
from pathlib import Path

# 数值计算
import numpy as np

# 从项目内部模块导入：根据四元数和平移构造 PoseSE3
from ..transforms import matrix_to_quaternion, pose_from_quaternion_translation
from .interpolation import interpolate_rigid_pose

# 项目中定义的位姿类型
from ..types import PoseSE3


# =========================================================
# 数据类：带时间戳的位姿
# =========================================================
@dataclass(slots=True)
class TimestampedPose:
    """
    表示某一时刻的位姿数据
    """
    timestamp_s: float   # 时间戳（秒）
    pose: PoseSE3        # 位姿对象

    @property
    def translation_m(self) -> np.ndarray:
        """为公共插值接口暴露平移向量。"""
        return self.pose.translation_m

    @property
    def quaternion_xyzw(self) -> np.ndarray:
        """为公共插值接口暴露 ``xyzw`` 四元数。"""
        return matrix_to_quaternion(self.pose.rotation)


# =========================================================
# 工具函数：规范化表头
# =========================================================
def _normalize_header(header: list[str]) -> list[str]:
    """
    去掉表头每个单元格前后的空白字符
    例如：
        [" timestamp ", " tx ", " ty "]
    变成：
        ["timestamp", "tx", "ty"]
    """
    return [cell.strip() for cell in header]


# =========================================================
# 工具函数：安全读取某一列
# =========================================================
def _cell(row: list[str], index: int) -> str:
    """
    安全获取 row[index] 的内容。
    如果索引越界，返回空字符串，而不是直接报错。
    """
    if 0 <= index < len(row):
        return row[index].strip()
    return ""


# =========================================================
# 工具函数：长度单位转换为米
# =========================================================
def _length_unit_scale_to_m(length_units: str) -> float:
    """
    根据字符串单位，返回到“米”的缩放系数。

    支持：
        m / meter / meters
        cm / centimeter / centimeters
        mm / millimeter / millimeters
    """
    units = length_units.strip().lower()

    # 米 -> 米
    if units in {"m", "meter", "meters"}:
        return 1.0

    # 厘米 -> 米
    if units in {"cm", "centimeter", "centimeters"}:
        return 0.01

    # 毫米 -> 米
    if units in {"mm", "millimeter", "millimeters"}:
        return 0.001

    # 不支持的单位直接报错
    raise ValueError(f"Unsupported FzMotion length unit: {length_units}")


# =========================================================
# 主类：从 CSV 提供刚体位姿
# =========================================================
class CSVRigidBodyProvider:
    """
    这个类的作用是：
    1. 读取动捕 CSV
    2. 自动识别 CSV 格式
    3. 解析出每个 rigid body 的所有位姿样本
    4. 支持按时间戳查询某个刚体最接近的位姿
    """

    def __init__(self, csv_path: str | Path) -> None:
        """
        初始化：
        - 保存 CSV 路径
        - 检查文件是否存在
        - 创建若干内部字典
        - 自动加载 CSV
        """
        self.csv_path = Path(csv_path)

        # 如果文件不存在，直接报错
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Mocap CSV not found: {self.csv_path}")

        # 存储 CSV 元信息（仅 FzMotion 格式常用）
        self.metadata: dict[str, str] = {}

        # 记录当前 CSV 的格式
        # 可能是 "fzmotion_csv" 或 "generic_pose_csv"
        self.source_format = "unknown"

        # 按刚体名称存储位姿样本
        # 结构：
        # {
        #   "camera_rigid": [TimestampedPose(...), TimestampedPose(...), ...],
        #   "board_rigid":  [TimestampedPose(...), TimestampedPose(...), ...],
        # }
        self._poses_by_body: dict[str, list[TimestampedPose]] = {}

        # 按刚体名称存储所有时间戳列表
        # 主要用于后面二分查找
        self._timestamps_by_body: dict[str, list[float]] = {}

        # 加载 CSV 数据
        self._load_csv()

    # -----------------------------------------------------
    # 内部函数：向某个刚体追加一条位姿
    # -----------------------------------------------------
    def _append_pose(
        self,
        rigid_body: str,
        timestamp_s: float,
        translation_m: np.ndarray,
        quaternion_xyzw: np.ndarray
    ) -> None:
        """
        把一条位姿样本加入指定刚体的样本列表中
        """
        # 构造项目内部统一的 PoseSE3 对象
        pose = pose_from_quaternion_translation(
            parent_frame="mocap_world",     # 父坐标系固定为动捕世界系
            child_frame=rigid_body,         # 子坐标系为该刚体
            translation_m=translation_m,    # 平移（单位：米）
            quaternion_xyzw=quaternion_xyzw,# 四元数
            timestamp_s=timestamp_s,        # 时间戳
        )

        # 把这条带时间戳的位姿存进去
        self._poses_by_body.setdefault(rigid_body, []).append(
            TimestampedPose(timestamp_s=timestamp_s, pose=pose)
        )

    # -----------------------------------------------------
    # 内部函数：加载 CSV，并自动识别格式
    # -----------------------------------------------------
    def _load_csv(self) -> None:
        """
        读取整个 CSV 文件，并根据首行判断格式：
        - 如果首行第一个单元格是 DataName，则按 FzMotion 格式读取
        - 否则按普通标准 CSV 格式读取
        """
        with self.csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            # 读取所有非空行
            rows = [row for row in csv.reader(handle) if any(cell.strip() for cell in row)]

        # CSV 完全为空则报错
        if not rows:
            raise ValueError(f"Mocap CSV is empty: {self.csv_path}")

        # 读取第一行并做 strip
        first_row = _normalize_header(rows[0])

        # 判断是不是 FzMotion 导出格式
        if first_row and first_row[0] == "DataName":
            self.source_format = "fzmotion_csv"
            self._load_fzmotion_csv(rows)
        else:
            self.source_format = "generic_pose_csv"
            self._load_standard_csv(rows)

        # 对每个刚体的样本按时间排序，并单独提取时间戳数组
        for rigid_body, samples in self._poses_by_body.items():
            # 按 timestamp_s 升序排序
            samples.sort(key=lambda item: item.timestamp_s)

            # 单独保存时间戳列表，方便后面二分查找
            self._timestamps_by_body[rigid_body] = [sample.timestamp_s for sample in samples]

    # -----------------------------------------------------
    # 读取标准 CSV
    # -----------------------------------------------------
    def _load_standard_csv(self, rows: list[list[str]]) -> None:
        """
        读取普通标准格式的 CSV

        需要至少包含这些列：
            timestamp, rigid_body, tx, ty, tz, qx, qy, qz, qw
        """
        # 第一行作为表头
        header = _normalize_header(rows[0])

        # 必需列
        required_columns = {"timestamp", "rigid_body", "tx", "ty", "tz", "qx", "qy", "qz", "qw"}

        # 如果缺列，直接报错
        if not required_columns.issubset(set(header)):
            raise ValueError(
                "Mocap CSV is missing required columns. "
                f"Expected at least: {sorted(required_columns)}"
            )

        # 逐行读取数据（跳过表头）
        for raw_row in rows[1:]:
            if not any(cell.strip() for cell in raw_row):
                continue

            # 把当前行转换为字典形式：列名 -> 值
            row = {
                header[index]: raw_row[index].strip() if index < len(raw_row) else ""
                for index in range(len(header))
            }

            # 刚体名字
            rigid_body = row["rigid_body"].strip()
            if not rigid_body:
                continue

            # 时间戳
            timestamp_s = float(row["timestamp"])

            # 平移向量
            translation = np.array([row["tx"], row["ty"], row["tz"]], dtype=np.float64)

            # 四元数
            quaternion = np.array([row["qx"], row["qy"], row["qz"], row["qw"]], dtype=np.float64)

            # 追加到内部数据结构中
            self._append_pose(rigid_body, timestamp_s, translation, quaternion)

    # -----------------------------------------------------
    # 读取 FzMotion CSV
    # -----------------------------------------------------
    def _load_fzmotion_csv(self, rows: list[list[str]]) -> None:
        """
        读取 FzMotion 导出的 CSV

        这种格式的特点：
        - 第0行：元数据（成对出现的 key/value）
        - 第1~5行：列语义说明
        - 第6行开始：真正的数据
        """
        # -------------------------
        # 1. 读取元数据
        # -------------------------
        metadata_row = _normalize_header(rows[0])

        # 按 key/value 成对读取
        for index in range(0, len(metadata_row) - 1, 2):
            key = metadata_row[index]
            value = metadata_row[index + 1]
            if key:
                self.metadata[key] = value

        # 根据 LengthUnits 确定位移单位到米的缩放
        unit_scale_to_m = _length_unit_scale_to_m(self.metadata.get("LengthUnits", "mm"))

        # -------------------------
        # 2. 读取几行结构描述
        # -------------------------
        type_row = _normalize_header(rows[1])      # 每列对应的实体类型
        name_row = _normalize_header(rows[2])      # 每列对应的实体名称
        semantic_row = _normalize_header(rows[4])  # 每列对应的语义：Rotation / Position
        axis_row = _normalize_header(rows[5])      # 每列对应的轴：X/Y/Z/W

        # 用来记录每个 rigid body 的列索引
        # 结构大概像：
        # {
        #   "camera_rigid": {
        #       "Rotation": {"X": 10, "Y": 11, "Z": 12, "W": 13},
        #       "Position": {"X": 14, "Y": 15, "Z": 16}
        #   }
        # }
        rigid_body_columns: dict[str, dict[str, dict[str, int]]] = {}

        # 有些行长度可能不一样，取最大列数防止漏掉
        max_columns = max(len(type_row), len(name_row), len(semantic_row), len(axis_row))

        # 逐列分析
        for column_index in range(max_columns):
            entity_type = _cell(type_row, column_index)       # 该列是不是 Rigid Body
            entity_name = _cell(name_row, column_index)       # 刚体名称
            semantic = _cell(semantic_row, column_index)      # Rotation / Position
            axis = _cell(axis_row, column_index).upper()      # X/Y/Z/W

            # 只关心 Rigid Body 类型
            if entity_type != "Rigid Body" or not entity_name:
                continue

            # 只关心旋转和位置
            if semantic not in {"Rotation", "Position"}:
                continue

            # 只关心 X/Y/Z/W 四个轴
            if axis not in {"X", "Y", "Z", "W"}:
                continue

            # 记录当前列索引
            rigid_body_columns.setdefault(entity_name, {"Rotation": {}, "Position": {}})[semantic][axis] = column_index

        # -------------------------
        # 3. 逐行读取数据部分
        # -------------------------
        for raw_row in rows[6:]:
            # 第1列（索引1）通常是时间戳
            timestamp_text = _cell(raw_row, 1)
            if not timestamp_text:
                continue

            timestamp_s = float(timestamp_text)

            # 对当前行中每个 rigid body 都尝试取值
            for rigid_body, columns in rigid_body_columns.items():
                rotation_columns = columns["Rotation"]
                position_columns = columns["Position"]

                # 必须有完整四元数和完整三维平移
                if not {"X", "Y", "Z", "W"}.issubset(rotation_columns):
                    continue
                if not {"X", "Y", "Z"}.issubset(position_columns):
                    continue

                try:
                    # 读取四元数
                    quaternion = np.array(
                        [
                            float(_cell(raw_row, rotation_columns["X"])),
                            float(_cell(raw_row, rotation_columns["Y"])),
                            float(_cell(raw_row, rotation_columns["Z"])),
                            float(_cell(raw_row, rotation_columns["W"])),
                        ],
                        dtype=np.float64,
                    )

                    # 读取平移，并按单位转换成米
                    translation = unit_scale_to_m * np.array(
                        [
                            float(_cell(raw_row, position_columns["X"])),
                            float(_cell(raw_row, position_columns["Y"])),
                            float(_cell(raw_row, position_columns["Z"])),
                        ],
                        dtype=np.float64,
                    )

                except ValueError:
                    # 如果某个单元格无法转成数字，则跳过当前刚体
                    continue

                # 保存当前刚体在这一时刻的位姿
                self._append_pose(rigid_body, timestamp_s, translation, quaternion)

    # -----------------------------------------------------
    # 列出所有刚体名称
    # -----------------------------------------------------
    def list_rigid_bodies(self) -> list[str]:
        """
        返回 CSV 中所有可用 rigid body 的名字
        """
        return sorted(self._poses_by_body.keys())

    # -----------------------------------------------------
    # 按时间戳查询某个刚体位姿
    # -----------------------------------------------------
    def get_pose(self, rigid_body: str, timestamp_s: float, max_time_diff_s: float) -> PoseSE3 | None:
        """
        查询某个刚体在给定时间戳附近最接近的一条位姿。

        参数:
            rigid_body: 刚体名称
            timestamp_s: 目标时间戳
            max_time_diff_s: 允许的最大时间差

        返回:
            PoseSE3 或 None
        """
        # 取出该刚体对应的时间戳数组和位姿数组
        timestamps = self._timestamps_by_body.get(rigid_body)
        samples = self._poses_by_body.get(rigid_body)

        # 如果这个刚体不存在，返回 None
        if not timestamps or not samples:
            return None

        # 用二分查找找到“应该插入的位置”
        insert_index = bisect.bisect_left(timestamps, timestamp_s)

        # 候选索引只需要考虑两个：
        # 1. 插入点本身
        # 2. 插入点前一个
        candidate_indexes = []

        if insert_index < len(timestamps):
            candidate_indexes.append(insert_index)

        if insert_index > 0:
            candidate_indexes.append(insert_index - 1)

        # 从候选中找时间差最小且不超过 max_time_diff_s 的一个
        best_pose = None
        best_delta = None

        for index in candidate_indexes:
            delta = abs(timestamps[index] - timestamp_s)

            if delta <= max_time_diff_s and (best_delta is None or delta < best_delta):
                best_delta = delta
                best_pose = samples[index].pose

        return best_pose

    def get_pose_window(
        self,
        rigid_body: str,
        timestamp_s: float,
        half_window_s: float,
    ) -> list[TimestampedPose]:
        """Return recorded poses inside a closed time window without interpolation."""
        if half_window_s < 0.0:
            raise ValueError("half_window_s must be non-negative")

        timestamps = self._timestamps_by_body.get(rigid_body)
        samples = self._poses_by_body.get(rigid_body)
        if not timestamps or not samples:
            return []

        start = bisect.bisect_left(timestamps, timestamp_s - half_window_s)
        end = bisect.bisect_right(timestamps, timestamp_s + half_window_s)
        return list(samples[start:end])

    def get_interpolated_pose(
        self,
        rigid_body: str,
        timestamp_s: float,
        max_gap_s: float | None = None,
    ) -> PoseSE3 | None:
        """线性插值平移并用 SLERP 插值旋转，默认不允许外推。"""
        samples = self._poses_by_body.get(rigid_body)
        result = interpolate_rigid_pose(samples or [], timestamp_s, max_gap_s=max_gap_s)
        if result is None:
            return None
        return pose_from_quaternion_translation(
            parent_frame="mocap_world",
            child_frame=rigid_body,
            translation_m=result.translation_m,
            quaternion_xyzw=result.quaternion_xyzw,
            timestamp_s=result.timestamp_s,
        )

    def query_pose(
        self,
        rigid_body: str,
        timestamp_s: float,
        *,
        mode: str = "nearest",
        max_time_diff_s: float | None = None,
        max_gap_s: float | None = None,
    ) -> PoseSE3 | None:
        """按显式模式查询位姿，旧流程默认仍为 ``nearest``。"""
        if mode == "nearest":
            if max_time_diff_s is None:
                raise ValueError("nearest mode requires max_time_diff_s")
            return self.get_pose(rigid_body, timestamp_s, max_time_diff_s)
        if mode == "interpolate":
            return self.get_interpolated_pose(rigid_body, timestamp_s, max_gap_s=max_gap_s)
        raise ValueError(f"Unsupported mocap query mode: {mode}")
