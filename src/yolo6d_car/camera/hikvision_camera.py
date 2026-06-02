"""海康工业相机封装，基于 MVS SDK 采集 RGB 图像。"""

from __future__ import annotations

from ctypes import POINTER, byref, c_bool, cast, c_ubyte, memset, sizeof, string_at
from dataclasses import dataclass, field
from pathlib import Path
import importlib
import os
import platform
import sys
import time
from typing import Any

import numpy as np


# 常见的 MVS Python 包目录候选路径。
_MVS_IMPORT_CANDIDATES = [
    Path(r"C:\Program Files (x86)\MVS\Development\Samples\64\Python\MvImport"),
    Path(r"C:\Program Files (x86)\MVS\Development\Samples\Python\MvImport"),
    Path(r"C:\Program Files (x86)\Common Files\MVS\Development\Samples\64\Python\MvImport"),
    Path(r"C:\Program Files (x86)\Common Files\MVS\Development\Samples\Python\MvImport"),
]

# 常见 MVS 运行库目录候选路径。
_MVS_DLL_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64"),
    Path(r"C:\Program Files (x86)\Common Files\MVS\Runtime\Win32_i86"),
]

# 常见像素格式别名。最终会映射到 SDK 中的 PixelType_* 常量。
_PIXEL_FORMAT_ALIASES = {
    "mono8": "PixelType_Gvsp_Mono8",
    "rgb8": "PixelType_Gvsp_RGB8_Packed",
    "rgb8packed": "PixelType_Gvsp_RGB8_Packed",
    "bgr8": "PixelType_Gvsp_BGR8_Packed",
    "bgr8packed": "PixelType_Gvsp_BGR8_Packed",
    "bayerrg8": "PixelType_Gvsp_BayerRG8",
    "bayerbg8": "PixelType_Gvsp_BayerBG8",
    "bayergr8": "PixelType_Gvsp_BayerGR8",
    "bayergb8": "PixelType_Gvsp_BayerGB8",
}


@dataclass(slots=True)
class HikvisionCamera:
    """海康工业相机采集类。"""

    device_index: int = 0
    exposure_time_us: float | None = None
    exposure_auto: str | int | None = "continuous"
    auto_exposure_upper_us: float | None = None
    gain_db: float | None = None
    gain_auto: str | int | None = "continuous"
    auto_gain_upper_db: float | None = None
    frame_rate: float | None = None
    width: int | None = None
    height: int | None = None
    gamma: float | None = None
    pixel_format: str | int | None = None
    grab_timeout_ms: int = 1000
    mvs_python_path: str | Path | None = None
    runtime_info_update_interval_s: float = 0.5
    _sdk: Any | None = field(init=False, default=None, repr=False)
    _camera: Any | None = field(init=False, default=None, repr=False)
    _device_info: Any | None = field(init=False, default=None, repr=False)
    _is_open: bool = field(init=False, default=False, repr=False)
    _is_grabbing: bool = field(init=False, default=False, repr=False)
    _last_pixel_type_name: str = field(init=False, default="UNKNOWN", repr=False)
    _last_mean_intensity: float = field(init=False, default=0.0, repr=False)
    _last_exposure_time_us: float = field(init=False, default=0.0, repr=False)
    _last_gain_db: float = field(init=False, default=0.0, repr=False)
    _last_exposure_auto: str = field(init=False, default="unknown", repr=False)
    _last_gain_auto: str = field(init=False, default="unknown", repr=False)
    _last_acquisition_frame_rate_fps: float = field(init=False, default=0.0, repr=False)
    _last_acquisition_frame_rate_enable: bool | None = field(init=False, default=None, repr=False)
    _last_runtime_info_update_ts: float = field(init=False, default=0.0, repr=False)

    def open(self) -> None:
        """加载 SDK、枚举设备并打开指定相机。"""
        if self._is_open:
            return None

        self._sdk = self._load_mvs_sdk(self.mvs_python_path)
        device_list = self._enum_devices(self._sdk)
        if self.device_index < 0 or self.device_index >= int(device_list.nDeviceNum):
            raise IndexError(
                f"请求的 device_index={self.device_index} 超出范围，当前只检测到 {device_list.nDeviceNum} 台海康相机。"
            )

        self._device_info = cast(
            device_list.pDeviceInfo[self.device_index],
            POINTER(self._sdk.MV_CC_DEVICE_INFO),
        ).contents

        self._camera = self._sdk.MvCamera()
        self._check_ret(self._camera.MV_CC_CreateHandle(self._device_info), "创建海康相机句柄失败")

        access_mode = getattr(self._sdk, "MV_ACCESS_Exclusive", 0)
        self._check_ret(self._camera.MV_CC_OpenDevice(access_mode, 0), "打开海康相机失败")

        # 连续采集 + 关闭硬触发。
        self._set_enum_value("TriggerMode", getattr(self._sdk, "MV_TRIGGER_MODE_OFF", 0), allow_fail=False)

        # 如果是 GigE，相机官方建议设置最佳包大小；USB3 相机会自动忽略这一步。
        self._try_set_optimal_packet_size()

        # 分辨率必须在开始取流前设置；不同型号会按允许范围和步进自动夹紧。
        if self.width is not None:
            self._set_int_value("Width", int(self.width), allow_fail=False)
        if self.height is not None:
            self._set_int_value("Height", int(self.height), allow_fail=False)

        # 如果用户显式给了曝光/增益，就优先关闭自动模式。
        if self.exposure_time_us is not None:
            self._set_enum_value("ExposureAuto", 0, allow_fail=True)
            self._set_float_value("ExposureTime", self.exposure_time_us, allow_fail=False)
        elif self.exposure_auto is not None:
            if self.auto_exposure_upper_us is not None:
                self._set_first_supported_int_value(
                    ["AutoExposureTimeUpperLimit", "AutoExposureTimeUpper", "ExposureTimeUpperLimit"],
                    int(round(self.auto_exposure_upper_us)),
                    allow_fail=True,
                )
            self._set_auto_enum_value("ExposureAuto", self.exposure_auto, allow_fail=True)

        if self.gain_db is not None:
            self._set_enum_value("GainAuto", 0, allow_fail=True)
            self._set_float_value("Gain", self.gain_db, allow_fail=False)
        elif self.gain_auto is not None:
            if self.auto_gain_upper_db is not None:
                self._set_first_supported_float_value(
                    ["AutoGainUpperLimit", "GainAutoUpperLimit", "GainUpperLimit"],
                    self.auto_gain_upper_db,
                    allow_fail=True,
                )
            self._set_auto_enum_value("GainAuto", self.gain_auto, allow_fail=True)

        if self.frame_rate is not None:
            self._set_bool_value("AcquisitionFrameRateEnable", True, allow_fail=True)
            self._set_float_value("AcquisitionFrameRate", self.frame_rate, allow_fail=False)

        # 默认不强行改相机输出像素格式，优先保留相机原始输出，再在主机侧做转换。
        if self.pixel_format is not None:
            pixel_format_value = self._resolve_pixel_format_value(self.pixel_format)
            self._set_enum_value("PixelFormat", pixel_format_value, allow_fail=False)

        if self.gamma is not None:
            self._set_gamma(self.gamma, allow_fail=True)

        self._try_enable_bayer_quality_settings()
        self._refresh_runtime_params(force=True)
        self._is_open = True
        return None

    def start(self) -> None:
        """启动取流。"""
        if not self._is_open:
            self.open()
        if self._is_grabbing:
            return None

        self._check_ret(self._camera.MV_CC_StartGrabbing(), "启动海康相机取流失败")
        self._is_grabbing = True
        return None

    def get_frame(self) -> tuple[int, float, np.ndarray]:
        """获取一帧图像，返回 (frame_id, timestamp, image_bgr)。"""
        if not self._is_grabbing:
            raise RuntimeError("必须先调用 start() 才能 get_frame()。")

        frame_out = self._sdk.MV_FRAME_OUT()
        memset(byref(frame_out), 0, sizeof(frame_out))
        ret = self._camera.MV_CC_GetImageBuffer(frame_out, int(self.grab_timeout_ms))
        self._check_ret(ret, "获取海康相机图像失败")

        try:
            frame_id = int(frame_out.stFrameInfo.nFrameNum)
            timestamp = self._extract_timestamp(frame_out.stFrameInfo)
            image = self._frame_to_bgr_image(frame_out)
            self._last_mean_intensity = float(np.mean(image))
            self._refresh_runtime_params()
        finally:
            self._camera.MV_CC_FreeImageBuffer(frame_out)

        return frame_id, timestamp, image

    def stop(self) -> None:
        """停止取流。"""
        if self._camera is None or not self._is_grabbing:
            return None

        self._check_ret(self._camera.MV_CC_StopGrabbing(), "停止海康相机取流失败")
        self._is_grabbing = False
        return None

    def close(self) -> None:
        """关闭相机并销毁句柄。"""
        if self._camera is None:
            self._is_open = False
            self._is_grabbing = False
            return None

        if self._is_grabbing:
            self.stop()

        try:
            self._camera.MV_CC_CloseDevice()
        finally:
            try:
                self._camera.MV_CC_DestroyHandle()
            finally:
                self._camera = None
                self._device_info = None
                self._is_open = False
                self._is_grabbing = False
        return None

    @property
    def last_pixel_type_name(self) -> str:
        """返回最近一帧的原始像素格式名称。"""
        return self._last_pixel_type_name

    @property
    def last_mean_intensity(self) -> float:
        """返回最近一帧图像的亮度均值。"""
        return self._last_mean_intensity

    @property
    def last_exposure_time_us(self) -> float:
        """返回最近一次读取到的曝光时间，单位微秒。"""
        return self._last_exposure_time_us

    @property
    def last_gain_db(self) -> float:
        """返回最近一次读取到的增益，单位 dB。"""
        return self._last_gain_db

    @property
    def last_exposure_auto(self) -> str:
        """返回最近一次读取到的自动曝光模式。"""
        return self._last_exposure_auto

    @property
    def last_gain_auto(self) -> str:
        """返回最近一次读取到的自动增益模式。"""
        return self._last_gain_auto

    @property
    def last_acquisition_frame_rate_fps(self) -> float:
        """返回最近一次读取到的相机帧率节点值。"""
        return self._last_acquisition_frame_rate_fps

    @property
    def last_acquisition_frame_rate_enable(self) -> bool | None:
        """返回最近一次读取到的帧率限制开关状态。"""
        return self._last_acquisition_frame_rate_enable

    @staticmethod
    def _load_mvs_sdk(mvs_python_path: str | Path | None) -> Any:
        """按优先级加载官方 MVS Python 包，并补充 DLL 搜索目录。"""
        candidate_paths: list[Path] = []

        if mvs_python_path is not None:
            candidate_paths.append(Path(mvs_python_path))

        for env_name in ["HIKROBOT_MVS_PYTHON_PATH", "MVS_PYTHON_PATH"]:
            env_value = os.environ.get(env_name)
            if env_value:
                candidate_paths.append(Path(env_value))

        common_runenv = os.environ.get("MVCAM_COMMON_RUNENV")
        if common_runenv:
            common_root = Path(common_runenv)
            candidate_paths.append(common_root / "Samples" / "Python" / "MvImport")
            candidate_paths.append(common_root / "MVFG" / "Samples" / "Python" / "MvImport")

        candidate_paths.extend(_MVS_IMPORT_CANDIDATES)
        HikvisionCamera._prepare_mvs_dll_search_dirs(common_runenv)

        tried_paths: list[str] = []
        for candidate in candidate_paths:
            if not candidate.exists():
                continue
            tried_paths.append(str(candidate))
            if str(candidate) not in sys.path:
                sys.path.insert(0, str(candidate))
            try:
                return importlib.import_module("MvCameraControl_class")
            except Exception:
                continue

        try:
            return importlib.import_module("MvCameraControl_class")
        except Exception as exc:
            extra = "\n".join(tried_paths) if tried_paths else "<未找到任何候选目录>"
            raise ImportError(
                "未能导入海康 MVS Python SDK。\n"
                "请先安装 MVS，并确认 MvCameraControl_class.py 可被 Python 找到。\n"
                f"已尝试目录：\n{extra}"
            ) from exc

    @staticmethod
    def _prepare_mvs_dll_search_dirs(common_runenv: str | None) -> None:
        """补充 Windows DLL 搜索路径，避免找不到 MvCameraControl.dll。"""
        dll_dirs: list[Path] = []
        dll_dirs.extend(_MVS_DLL_CANDIDATES)

        if common_runenv:
            common_root = Path(common_runenv)
            if platform.system().lower() == "windows":
                dll_dirs.append(common_root)
                dll_dirs.append(common_root / "Runtime" / "Win64_x64")
                dll_dirs.append(common_root / "Runtime" / "Win32_i86")

        existing_path = os.environ.get("PATH", "")
        path_parts = existing_path.split(os.pathsep) if existing_path else []
        for dll_dir in dll_dirs:
            if not dll_dir.exists():
                continue
            dll_dir_str = str(dll_dir)
            try:
                if hasattr(os, "add_dll_directory"):
                    os.add_dll_directory(dll_dir_str)
            except Exception:
                pass
            if dll_dir_str not in path_parts:
                path_parts.insert(0, dll_dir_str)
        os.environ["PATH"] = os.pathsep.join(path_parts)

    @staticmethod
    def _enum_devices(sdk: Any) -> Any:
        """枚举海康设备列表。"""
        transport_mask = 0
        for constant_name in [
            "MV_GIGE_DEVICE",
            "MV_USB_DEVICE",
            "MV_GENTL_GIGE_DEVICE",
            "MV_GENTL_CAMERALINK_DEVICE",
            "MV_GENTL_CXP_DEVICE",
            "MV_GENTL_XOF_DEVICE",
        ]:
            transport_mask |= int(getattr(sdk, constant_name, 0))
        if transport_mask == 0:
            transport_mask = int(getattr(sdk, "MV_USB_DEVICE", 2))

        sdk.MvCamera.MV_CC_Initialize()
        device_list = sdk.MV_CC_DEVICE_INFO_LIST()
        memset(byref(device_list), 0, sizeof(device_list))
        ret = sdk.MvCamera.MV_CC_EnumDevices(transport_mask, device_list)
        HikvisionCamera._check_ret(ret, "枚举海康相机失败")
        if int(device_list.nDeviceNum) <= 0:
            raise RuntimeError("未检测到海康工业相机，请检查 USB3.0 连接和 MVS 驱动。")
        return device_list

    def _try_set_optimal_packet_size(self) -> None:
        """GigE 相机时尝试设置最佳包大小。"""
        try:
            n_packet_size = int(self._camera.MV_CC_GetOptimalPacketSize())
            if n_packet_size > 0:
                self._camera.MV_CC_SetIntValue("GevSCPSPacketSize", n_packet_size)
        except Exception:
            pass

    def _try_enable_bayer_quality_settings(self) -> None:
        """尽量开启更好的 Bayer 转彩色参数。"""
        try:
            self._camera.MV_CC_SetBayerCvtQuality(2)
        except Exception:
            pass
        try:
            self._camera.MV_CC_SetBayerFilterEnable(True)
        except Exception:
            pass

    def _resolve_pixel_format_value(self, pixel_format: str | int) -> int:
        """把用户输入的像素格式解析成 SDK 枚举值。"""
        if isinstance(pixel_format, int):
            return int(pixel_format)

        raw_key = str(pixel_format).strip()
        normalized = raw_key.lower().replace("_", "").replace("-", "")
        constant_name = _PIXEL_FORMAT_ALIASES.get(normalized, raw_key)
        if hasattr(self._sdk, constant_name):
            return int(getattr(self._sdk, constant_name))
        raise ValueError(f"不支持的 pixel_format: {pixel_format}")

    def _resolve_auto_mode_value(self, mode: str | int) -> int:
        """把自动曝光/自动增益模式解析成 SDK 枚举值。"""
        if isinstance(mode, int):
            return int(mode)

        normalized = str(mode).strip().lower().replace("_", "").replace("-", "")
        if normalized in {"off", "0"}:
            return 0
        if normalized in {"once", "1"}:
            return 1
        if normalized in {"continuous", "cont", "auto", "2"}:
            return 2
        raise ValueError(f"不支持的自动参数模式: {mode}")

    @staticmethod
    def _auto_mode_name(mode_value: int) -> str:
        """把 SDK 自动模式枚举值转成人可读文本。"""
        if int(mode_value) == 0:
            return "off"
        if int(mode_value) == 1:
            return "once"
        if int(mode_value) == 2:
            return "continuous"
        return f"unknown({mode_value})"

    def _frame_to_bgr_image(self, frame_out: Any) -> np.ndarray:
        """把 SDK 图像缓存转为 OpenCV 可直接使用的 BGR ndarray。"""
        frame_info = frame_out.stFrameInfo
        width = int(frame_info.nWidth)
        height = int(frame_info.nHeight)
        src_pixel_type = int(frame_info.enPixelType)
        src_len = int(frame_info.nFrameLen)
        src_data_ptr = frame_out.pBufAddr

        self._last_pixel_type_name = self._pixel_type_name(src_pixel_type)

        # 如果是高带宽压缩格式，先按官方样例做 HB 解码。
        if self._is_hb_pixel_type_name(self._last_pixel_type_name):
            src_data_ptr, src_len, src_pixel_type = self._hb_decode(frame_out)
            self._last_pixel_type_name = self._pixel_type_name(src_pixel_type)

        # Mono8 可以直接扩成三通道，避免额外转换开销。
        if self._last_pixel_type_name == "PixelType_Gvsp_Mono8":
            raw_bytes = string_at(src_data_ptr, src_len)
            gray = np.frombuffer(raw_bytes, dtype=np.uint8).reshape(height, width)
            return np.repeat(gray[:, :, None], 3, axis=2).copy()

        # BGR8 / RGB8 直接 reshape，避免不必要的 SDK 转换。
        if self._last_pixel_type_name == "PixelType_Gvsp_BGR8_Packed":
            raw_bytes = string_at(src_data_ptr, src_len)
            return np.frombuffer(raw_bytes, dtype=np.uint8).reshape(height, width, 3).copy()
        if self._last_pixel_type_name == "PixelType_Gvsp_RGB8_Packed":
            raw_bytes = string_at(src_data_ptr, src_len)
            rgb = np.frombuffer(raw_bytes, dtype=np.uint8).reshape(height, width, 3)
            return rgb[:, :, ::-1].copy()

        # Bayer / 其他格式统一交给 SDK 转成 BGR8。
        return self._convert_with_sdk(
            width=width,
            height=height,
            src_pixel_type=src_pixel_type,
            src_len=src_len,
            src_data_ptr=src_data_ptr,
            dst_pixel_format_name="PixelType_Gvsp_BGR8_Packed",
        )

    def _hb_decode(self, frame_out: Any) -> tuple[Any, int, int]:
        """把高带宽压缩图像解码回普通像素流。"""
        frame_info = frame_out.stFrameInfo
        decode_need_buffer_len = int(frame_info.nWidth) * int(frame_info.nHeight) * 3
        decode_buffer = (c_ubyte * decode_need_buffer_len)()

        decode_param = self._sdk.MV_CC_HB_DECODE_PARAM()
        memset(byref(decode_param), 0, sizeof(decode_param))
        decode_param.pSrcBuf = frame_out.pBufAddr
        decode_param.nSrcLen = int(frame_info.nFrameLen)
        decode_param.nWidth = int(frame_info.nWidth)
        decode_param.nHeight = int(frame_info.nHeight)
        decode_param.pDstBuf = cast(decode_buffer, POINTER(c_ubyte))
        decode_param.nDstBufSize = decode_need_buffer_len

        self._check_ret(self._camera.MV_CC_HBDecode(decode_param), "HB 图像解码失败")
        return decode_param.pDstBuf, int(decode_param.nDstBufLen), int(decode_param.enDstPixelType)

    def _convert_with_sdk(
        self,
        width: int,
        height: int,
        src_pixel_type: int,
        src_len: int,
        src_data_ptr: Any,
        dst_pixel_format_name: str,
    ) -> np.ndarray:
        """使用 MVS SDK 完成像素格式转换。"""
        dst_pixel_type = self._resolve_pixel_format_value(dst_pixel_format_name)
        dst_buffer_size = width * height * 3
        dst_buffer = (c_ubyte * dst_buffer_size)()

        # 优先走官方 OpenCV 样例里的 Ex 接口。
        if hasattr(self._sdk, "MV_CC_PIXEL_CONVERT_PARAM_EX") and hasattr(self._camera, "MV_CC_ConvertPixelTypeEx"):
            convert_param = self._sdk.MV_CC_PIXEL_CONVERT_PARAM_EX()
            memset(byref(convert_param), 0, sizeof(convert_param))
            convert_param.nWidth = width
            convert_param.nHeight = height
            convert_param.pSrcData = src_data_ptr
            convert_param.nSrcDataLen = int(src_len)
            convert_param.enSrcPixelType = int(src_pixel_type)
            convert_param.enDstPixelType = int(dst_pixel_type)
            convert_param.pDstBuffer = cast(dst_buffer, POINTER(c_ubyte))
            convert_param.nDstBufferSize = dst_buffer_size
            self._check_ret(
                self._camera.MV_CC_ConvertPixelTypeEx(convert_param),
                f"像素格式转换失败，源格式={self._pixel_type_name(src_pixel_type)}",
            )
            dst_len = int(getattr(convert_param, "nDstLen", dst_buffer_size))
        else:
            convert_param = self._sdk.MV_CC_PIXEL_CONVERT_PARAM()
            memset(byref(convert_param), 0, sizeof(convert_param))
            convert_param.nWidth = width
            convert_param.nHeight = height
            convert_param.pSrcData = src_data_ptr
            convert_param.nSrcDataLen = int(src_len)
            convert_param.enSrcPixelType = int(src_pixel_type)
            convert_param.enDstPixelType = int(dst_pixel_type)
            convert_param.pDstBuffer = cast(dst_buffer, POINTER(c_ubyte))
            convert_param.nDstBufferSize = dst_buffer_size
            self._check_ret(
                self._camera.MV_CC_ConvertPixelType(convert_param),
                f"像素格式转换失败，源格式={self._pixel_type_name(src_pixel_type)}",
            )
            dst_len = int(getattr(convert_param, "nDstLen", dst_buffer_size))

        image = np.frombuffer(dst_buffer, dtype=np.uint8, count=dst_len)
        return image.reshape(height, width, 3).copy()

    def _pixel_type_name(self, pixel_type_value: int) -> str:
        """反查当前像素格式名称，便于报错和日志。"""
        for attr_name in dir(self._sdk):
            if not attr_name.startswith("PixelType_"):
                continue
            try:
                if int(getattr(self._sdk, attr_name)) == int(pixel_type_value):
                    return attr_name
            except Exception:
                continue
        return f"UNKNOWN({pixel_type_value})"

    @staticmethod
    def _is_hb_pixel_type_name(pixel_type_name: str) -> bool:
        """判断是否为高带宽压缩像素格式。"""
        return pixel_type_name.startswith("PixelType_Gvsp_HB_")

    def _extract_timestamp(self, frame_info: Any) -> float:
        """尽量从 SDK 元信息中提取时间戳，失败时退回系统时间。"""
        host_timestamp = int(getattr(frame_info, "nHostTimeStamp", 0) or 0)
        if host_timestamp > 0:
            if host_timestamp > 10**15:
                return float(host_timestamp) / 1e9
            if host_timestamp > 10**12:
                return float(host_timestamp) / 1e6
            if host_timestamp > 10**9:
                return float(host_timestamp) / 1e3
            return float(host_timestamp)

        dev_high = int(getattr(frame_info, "nDevTimeStampHigh", 0) or 0)
        dev_low = int(getattr(frame_info, "nDevTimeStampLow", 0) or 0)
        dev_timestamp = (dev_high << 32) | dev_low
        if dev_timestamp > 0:
            return float(dev_timestamp)

        return time.time()

    def _set_enum_value(self, key: str, value: int, allow_fail: bool) -> None:
        ret = self._camera.MV_CC_SetEnumValue(key, int(value))
        self._check_optional_ret(ret, f"设置枚举参数 {key} 失败", allow_fail)

    def _set_auto_enum_value(self, key: str, mode: str | int, allow_fail: bool) -> None:
        """设置自动曝光/自动增益等自动模式节点。"""
        value = self._resolve_auto_mode_value(mode)
        self._set_enum_value(key, value, allow_fail=allow_fail)

    def _set_float_value(self, key: str, value: float, allow_fail: bool) -> None:
        requested_value = float(value)
        value_info = self._get_float_value_info(key)
        applied_value = requested_value

        if value_info is not None:
            min_value = float(value_info.fMin)
            max_value = float(value_info.fMax)
            applied_value = min(max(requested_value, min_value), max_value)
            if abs(applied_value - requested_value) > 1e-9:
                print(
                    f"[HikvisionCamera] 参数 {key} 请求值 {requested_value:.3f} 超出范围，"
                    f"已自动夹紧到 {applied_value:.3f}，允许范围 [{min_value:.3f}, {max_value:.3f}]。"
                )

        ret = self._camera.MV_CC_SetFloatValue(key, applied_value)
        self._check_optional_ret(ret, f"设置浮点参数 {key} 失败", allow_fail)

    def _set_first_supported_float_value(self, keys: list[str], value: float, allow_fail: bool) -> None:
        """按候选节点名设置浮点参数，兼容不同海康型号的 GenICam 命名差异。"""
        last_ret = None
        for key in keys:
            try:
                ret = self._camera.MV_CC_SetFloatValue(key, float(value))
                if int(ret) == 0:
                    return None
                last_ret = ret
            except Exception:
                continue
        self._check_optional_ret(last_ret if last_ret is not None else -1, f"设置浮点参数 {keys} 失败", allow_fail)

    def _set_bool_value(self, key: str, value: bool, allow_fail: bool) -> None:
        ret = self._camera.MV_CC_SetBoolValue(key, bool(value))
        self._check_optional_ret(ret, f"设置布尔参数 {key} 失败", allow_fail)

    def _set_int_value(self, key: str, value: int, allow_fail: bool) -> None:
        requested_value = int(value)
        value_info = self._get_int_value_info(key)
        applied_value = requested_value

        if value_info is not None:
            min_value = int(value_info.nMin)
            max_value = int(value_info.nMax)
            inc_value = max(int(getattr(value_info, "nInc", 1) or 1), 1)
            applied_value = min(max(requested_value, min_value), max_value)
            applied_value = min_value + ((applied_value - min_value) // inc_value) * inc_value
            if applied_value != requested_value:
                print(
                    f"[HikvisionCamera] 参数 {key} 请求值 {requested_value} 超出范围或不满足步进，"
                    f"已自动调整到 {applied_value}，允许范围 [{min_value}, {max_value}]，步进 {inc_value}。"
                )

        if hasattr(self._camera, "MV_CC_SetIntValueEx"):
            ret = self._camera.MV_CC_SetIntValueEx(key, int(applied_value))
        else:
            ret = self._camera.MV_CC_SetIntValue(key, int(applied_value))
        self._check_optional_ret(ret, f"设置整数参数 {key} 失败", allow_fail)

    def _set_first_supported_int_value(self, keys: list[str], value: int, allow_fail: bool) -> None:
        """按候选节点名设置整数参数，失败时按 allow_fail 决定是否继续。"""
        last_ret = None
        for key in keys:
            try:
                if hasattr(self._camera, "MV_CC_SetIntValueEx"):
                    ret = self._camera.MV_CC_SetIntValueEx(key, int(value))
                else:
                    ret = self._camera.MV_CC_SetIntValue(key, int(value))
                if int(ret) == 0:
                    return None
                last_ret = ret
            except Exception:
                continue
        self._check_optional_ret(last_ret if last_ret is not None else -1, f"设置整数参数 {keys} 失败", allow_fail)

    def _set_gamma(self, gamma: float, allow_fail: bool) -> None:
        """设置相机侧 Gamma；如果当前型号不支持，允许静默跳过。"""
        gamma_value = float(min(max(gamma, 0.1), 4.0))
        self._set_bool_value("GammaEnable", True, allow_fail=True)
        ret = self._camera.MV_CC_SetFloatValue("Gamma", gamma_value)
        if int(ret) == 0:
            return None

        if hasattr(self._camera, "MV_CC_SetGammaValue"):
            src_pixel_type = self._resolve_pixel_format_value(self.pixel_format or "RGB8Packed")
            ret = self._camera.MV_CC_SetGammaValue(src_pixel_type, gamma_value)
        self._check_optional_ret(ret, f"设置 Gamma 失败", allow_fail)

    def _get_float_value(self, key: str) -> float | None:
        """读取海康浮点参数，失败时返回 None，避免影响主流程。"""
        st_value = self._get_float_value_info(key)
        if st_value is None:
            return None
        return float(st_value.fCurValue)

    def _get_int_value_info(self, key: str) -> Any | None:
        """读取海康整数参数完整信息，包括当前值、范围和步进。"""
        try:
            if hasattr(self._sdk, "MVCC_INTVALUE_EX") and hasattr(self._camera, "MV_CC_GetIntValueEx"):
                st_value = self._sdk.MVCC_INTVALUE_EX()
                memset(byref(st_value), 0, sizeof(st_value))
                ret = self._camera.MV_CC_GetIntValueEx(key, st_value)
            else:
                st_value = self._sdk.MVCC_INTVALUE()
                memset(byref(st_value), 0, sizeof(st_value))
                ret = self._camera.MV_CC_GetIntValue(key, st_value)
            if int(ret) != 0:
                return None
            return st_value
        except Exception:
            return None

    def _get_float_value_info(self, key: str) -> Any | None:
        """读取海康浮点参数完整信息，包括当前值和上下限。"""
        try:
            st_value = self._sdk.MVCC_FLOATVALUE()
            memset(byref(st_value), 0, sizeof(st_value))
            ret = self._camera.MV_CC_GetFloatValue(key, st_value)
            if int(ret) != 0:
                return None
            return st_value
        except Exception:
            return None

    def _get_enum_value(self, key: str) -> int | None:
        """读取海康枚举参数，失败时返回 None。"""
        try:
            st_value = self._sdk.MVCC_ENUMVALUE()
            memset(byref(st_value), 0, sizeof(st_value))
            ret = self._camera.MV_CC_GetEnumValue(key, st_value)
            if int(ret) != 0:
                return None
            return int(st_value.nCurValue)
        except Exception:
            return None

    def _get_bool_value(self, key: str) -> bool | None:
        """读取海康布尔参数，失败时返回 None。"""
        try:
            bool_value = c_bool(False)
            ret = self._camera.MV_CC_GetBoolValue(key, bool_value)
            if int(ret) != 0:
                return None
            return bool(bool_value.value)
        except Exception:
            return None

    def _refresh_runtime_params(self, force: bool = False) -> None:
        """低频刷新当前曝光/增益/帧率等调试参数，减少预览线程额外开销。"""
        now = time.perf_counter()
        if not force and (now - self._last_runtime_info_update_ts) < float(self.runtime_info_update_interval_s):
            return None

        exposure = self._get_float_value("ExposureTime")
        gain = self._get_float_value("Gain")
        exposure_auto = self._get_enum_value("ExposureAuto")
        gain_auto = self._get_enum_value("GainAuto")
        acquisition_frame_rate = self._get_float_value("AcquisitionFrameRate")
        acquisition_frame_rate_enable = self._get_bool_value("AcquisitionFrameRateEnable")

        if exposure is not None:
            self._last_exposure_time_us = exposure
        if gain is not None:
            self._last_gain_db = gain
        if exposure_auto is not None:
            self._last_exposure_auto = self._auto_mode_name(exposure_auto)
        if gain_auto is not None:
            self._last_gain_auto = self._auto_mode_name(gain_auto)
        if acquisition_frame_rate is not None:
            self._last_acquisition_frame_rate_fps = acquisition_frame_rate
        if acquisition_frame_rate_enable is not None:
            self._last_acquisition_frame_rate_enable = acquisition_frame_rate_enable
        self._last_runtime_info_update_ts = now
        return None

    @staticmethod
    def _check_optional_ret(ret_code: int, message: str, allow_fail: bool) -> None:
        if int(ret_code) == 0:
            return None
        if allow_fail:
            return None
        HikvisionCamera._check_ret(ret_code, message)

    @staticmethod
    def _check_ret(ret_code: int, message: str) -> None:
        if int(ret_code) != 0:
            raise RuntimeError(f"{message}，错误码: 0x{int(ret_code) & 0xFFFFFFFF:08X}")
