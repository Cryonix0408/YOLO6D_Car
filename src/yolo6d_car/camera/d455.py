"""RealSense D455 取流封装，负责图像、深度和内参读取。"""

from __future__ import annotations

from dataclasses import dataclass, field
import warnings

import numpy as np

from ..config import CameraConfig
from ..types import CameraIntrinsics, ImageFrame


# ------------------------------------------------------------
# D455 相机数据流类
# 作用：
#   1. 启动相机
#   2. 获取 RGB / Depth 数据
#   3. 读取相机内参
#   4. 输出统一格式的 ImageFrame
# ------------------------------------------------------------
@dataclass(slots=True)
class D455Stream:
    # 相机配置（分辨率、fps、是否启用深度等）
    config: CameraConfig
    _pipeline: object | None = field(init=False, default=None, repr=False)
    _align: object | None = field(init=False, default=None, repr=False)
    _intrinsics: CameraIntrinsics | None = field(init=False, default=None, repr=False)
    _depth_enabled: bool = field(init=False, default=False, repr=False)
    _active_depth_size: tuple[int, int] | None = field(init=False, default=None, repr=False)
    _frame_timeout_ms: int = field(init=False, default=10000, repr=False)
    _frame_retry_count: int = field(init=False, default=3, repr=False)

    def __post_init__(self) -> None:
        return None

    def _build_stream_config(self, rs, enable_depth: bool, depth_size: tuple[int, int] | None):
        rs_config = rs.config()
        rs_config.enable_stream(
            rs.stream.color,
            self.config.color_width,
            self.config.color_height,
            rs.format.bgr8,
            self.config.fps,
        )
        if enable_depth:
            depth_width, depth_height = depth_size if depth_size is not None else (
                self.config.color_width,
                self.config.color_height,
            )
            rs_config.enable_stream(
                rs.stream.depth,
                depth_width,
                depth_height,
                rs.format.z16,
                self.config.fps,
            )
        return rs_config

    def _initialize_from_profile(self, rs, profile, enable_depth: bool, depth_size: tuple[int, int] | None) -> None:
        self._depth_enabled = enable_depth
        self._active_depth_size = depth_size if enable_depth else None
        self._align = rs.align(rs.stream.color) if enable_depth and self.config.align_depth_to_color else None

        color_profile = profile.get_stream(rs.stream.color).as_video_stream_profile()
        intrinsics = color_profile.get_intrinsics()
        self._intrinsics = CameraIntrinsics(
            fx=float(intrinsics.fx),
            fy=float(intrinsics.fy),
            cx=float(intrinsics.ppx),
            cy=float(intrinsics.ppy),
            width=int(intrinsics.width),
            height=int(intrinsics.height),
            dist_coeffs=np.asarray(intrinsics.coeffs, dtype=np.float64),
        )

    # ------------------------------------------------------------
    # 启动相机
    # ------------------------------------------------------------
    def start(self) -> None:
        try:
            import pyrealsense2 as rs
        except ImportError as exc:
            raise RuntimeError(
                "需要 pyrealsense2 才能使用 D455，相机 SDK 未安装"
            ) from exc

        attempts: list[tuple[bool, tuple[int, int] | None]] = []
        if self.config.enable_depth:
            seen_sizes: set[tuple[int, int]] = set()
            for depth_size in [
                (self.config.color_width, self.config.color_height),
                (848, 480),
                (640, 480),
            ]:
                if depth_size not in seen_sizes:
                    attempts.append((True, depth_size))
                    seen_sizes.add(depth_size)
            # 标定板采集并不依赖深度，所以最后允许退回到彩色-only
            attempts.append((False, None))
        else:
            attempts.append((False, None))

        last_error: RuntimeError | None = None
        tried_modes: list[str] = []

        for enable_depth, depth_size in attempts:
            pipeline = rs.pipeline()
            rs_config = self._build_stream_config(rs, enable_depth=enable_depth, depth_size=depth_size)
            mode_text = (
                f"color={self.config.color_width}x{self.config.color_height}@{self.config.fps}, "
                f"depth={'off' if not enable_depth else f'{depth_size[0]}x{depth_size[1]}@{self.config.fps}'}"
            )
            tried_modes.append(mode_text)

            try:
                profile = pipeline.start(rs_config)
                self._pipeline = pipeline
                self._initialize_from_profile(rs, profile, enable_depth=enable_depth, depth_size=depth_size)

                if self.config.enable_depth and not enable_depth:
                    warnings.warn(
                        "D455 depth stream could not be started with the requested settings; "
                        "falling back to color-only mode.",
                        RuntimeWarning,
                    )
                elif self.config.enable_depth and depth_size != (self.config.color_width, self.config.color_height):
                    warnings.warn(
                        f"D455 depth stream fell back to {depth_size[0]}x{depth_size[1]}@{self.config.fps}.",
                        RuntimeWarning,
                    )
                return None
            except RuntimeError as exc:
                last_error = exc
                try:
                    pipeline.stop()
                except Exception:
                    pass

        tried_modes_text = "; ".join(tried_modes)
        raise RuntimeError(
            "D455 启动失败，无法匹配当前请求的流配置。"
            f" 已尝试：{tried_modes_text}。"
            f" 最后一次错误：{last_error}."
            " 请先确认：1) 相机没有被 RealSense Viewer / 其他程序占用；"
            "2) 接在 USB 3.0 口；3) 如果只是采标定板，允许关闭 depth。"
        ) from last_error

    # ------------------------------------------------------------
    # 停止相机
    # ------------------------------------------------------------
    def stop(self) -> None:
        if self._pipeline is not None:
            self._pipeline.stop()
            self._pipeline = None
        self._align = None
        self._intrinsics = None
        self._depth_enabled = False
        self._active_depth_size = None

    # ------------------------------------------------------------
    # 获取一帧图像
    # ------------------------------------------------------------
    def wait_for_frame(self) -> ImageFrame:
        # 确保相机已启动
        if self._pipeline is None or self._intrinsics is None:
            raise RuntimeError("必须先调用 start()")

        frames = None
        last_error: RuntimeError | None = None
        for _ in range(self._frame_retry_count):
            try:
                frames = self._pipeline.wait_for_frames(self._frame_timeout_ms)
                break
            except RuntimeError as exc:
                last_error = exc
                continue

        if frames is None:
            raise RuntimeError(
                f"D455 在 {self._frame_retry_count} 次尝试后仍未返回图像帧。"
                f" 单次超时时间为 {self._frame_timeout_ms} ms。"
                f" 最后一次错误：{last_error}."
                " 请检查相机是否重新掉线、USB 线是否松动，或先拔插相机后重试。"
            ) from last_error

        # 如果启用对齐，则把 depth 对齐到 color
        if self._align is not None:
            frames = self._align.process(frames)

        # 获取 RGB 图像
        color_frame = frames.get_color_frame()
        if not color_frame:
            raise RuntimeError("获取 RGB 图像失败")

        # 转成 numpy
        color = np.asanyarray(color_frame.get_data()).copy()

        # --------------------------------------------------------
        # 获取深度图（可选）
        # --------------------------------------------------------
        depth = None
        if self._depth_enabled:
            depth_frame = frames.get_depth_frame()
            if depth_frame:
                depth = np.asanyarray(depth_frame.get_data()).copy()

        # 时间戳（毫秒 → 秒）
        timestamp_s = float(color_frame.get_timestamp()) / 1000.0

        # --------------------------------------------------------
        # 返回统一格式的数据结构
        # --------------------------------------------------------
        return ImageFrame(
            color=color,
            depth=depth,
            timestamp_s=timestamp_s,
            intrinsics=self._intrinsics,
        )

