"""本文件作用：
    自动采集标定板样本，用于 Hikrobot/OpenCV 相机标定。

在 YOLO6D_Car pipeline 中的位置：
    calibration capture 阶段。用户移动棋盘格，程序自动判断是否值得保存。

自动保存条件：
    棋盘格检测成功、图像清晰、覆盖比例足够、与已有样本差异足够、间隔时间足够。

注意事项：
    s 键只是备用手动保存；主流程应该依靠自动采样，避免一个人采集时频繁按键。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from .board_detector import BoardDetection, detect_board, draw_chessboard_debug
from .calibration_io import ensure_session_dirs, save_corners_json, write_json
from .calibration_quality import QualityDecision, evaluate_sample_quality


@dataclass(frozen=True, slots=True)
class CaptureSessionResult:
    """Summary returned by automatic calibration capture."""

    session_dir: Path
    saved_samples: int
    should_calibrate: bool
    stopped_reason: str


class OpenCVCameraSource:
    """Small OpenCV VideoCapture fallback used when Hik SDK is unavailable."""

    def __init__(self, camera_config: dict[str, Any]) -> None:
        self.camera_config = camera_config
        self.device_index = int(camera_config.get("device_index", 0))
        self.cap = None

    def start(self) -> None:
        """Open the camera and apply best-effort capture properties."""
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("opencv-python is required for camera capture fallback.") from exc

        self.cap = cv2.VideoCapture(self.device_index)
        if not self.cap.isOpened():
            raise RuntimeError(
                "Could not open camera through OpenCV VideoCapture. "
                "Install/configure Hikrobot SDK or check the camera index/connection."
            )
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(self.camera_config.get("width", 1440)))
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(self.camera_config.get("height", 1080)))
        self.cap.set(cv2.CAP_PROP_FPS, int(self.camera_config.get("fps", 30)))

    def read(self) -> np.ndarray:
        """Read one BGR frame."""
        if self.cap is None:
            raise RuntimeError("Camera source has not been started.")
        ok, frame = self.cap.read()
        if not ok or frame is None:
            raise RuntimeError("Camera frame read failed.")
        return frame

    def stop(self) -> None:
        """Release the camera if opened."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None


class HikvisionMVSCameraSource:
    """Hikvision MVS SDK camera source used by industrial-camera calibration."""

    def __init__(self, camera_config: dict[str, Any]) -> None:
        self.camera_config = camera_config
        self.camera = None

    def start(self) -> None:
        """Open the Hikvision camera through the same backend used by sequence capture."""
        from yolo6d_car.camera.hikvision_camera import HikvisionCamera

        pixel_format = self.camera_config.get("pixel_format")
        if pixel_format is not None and str(pixel_format).lower() == "auto":
            pixel_format = None

        self.camera = HikvisionCamera(
            device_index=int(self.camera_config.get("device_index", 0)),
            exposure_time_us=self.camera_config.get("exposure_us"),
            exposure_auto=None if self.camera_config.get("exposure_us") is not None else "continuous",
            gain_db=self.camera_config.get("gain"),
            gain_auto=None if self.camera_config.get("gain") is not None else "continuous",
            frame_rate=self.camera_config.get("fps"),
            width=self.camera_config.get("width"),
            height=self.camera_config.get("height"),
            pixel_format=pixel_format,
            mvs_python_path=self.camera_config.get("mvs_python_path"),
        )
        self.camera.open()
        self.camera.start()

    def read(self) -> np.ndarray:
        """Read one BGR frame from the Hikvision backend."""
        if self.camera is None:
            raise RuntimeError("Camera source has not been started.")
        _frame_id, _timestamp, image = self.camera.get_frame()
        return image

    def stop(self) -> None:
        """Stop and close the Hikvision camera."""
        if self.camera is not None:
            self.camera.stop()
            self.camera.close()
            self.camera = None


def create_camera_source(camera_config: dict[str, Any]) -> OpenCVCameraSource | HikvisionMVSCameraSource:
    """Create a camera source.

    Hikrobot/Hikvision industrial cameras should use the MVS backend. OpenCV is
    kept only as a fallback for webcams or quick local tests.
    """
    backend = str(camera_config.get("backend", "")).lower()
    name = str(camera_config.get("name", "")).lower()
    if backend in {"hikvision_mvs", "mvs"} or "hik" in name or "mv-cs" in name:
        return HikvisionMVSCameraSource(camera_config)
    return OpenCVCameraSource(camera_config)


def save_sample(
    *,
    dirs: dict[str, Path],
    sample_index: int,
    image_bgr: np.ndarray,
    debug_bgr: np.ndarray,
    corners: np.ndarray,
    detection: BoardDetection,
    decision: QualityDecision,
    config: dict[str, Any],
) -> None:
    """Persist one accepted calibration sample and metadata."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python is required for saving calibration images.") from exc

    sample_id = sample_index + 1
    stem = f"sample_{sample_id:06d}"
    raw_path = dirs["raw_images"] / f"{stem}.png"
    debug_path = dirs["debug_corners"] / f"{stem}.png"
    corners_npy = dirs["samples"] / f"{stem}_corners.npy"
    metadata_path = dirs["samples"] / f"{stem}_metadata.json"

    cv2.imwrite(str(raw_path), image_bgr)
    if bool(config["capture"].get("save_debug_images", True)):
        cv2.imwrite(str(debug_path), debug_bgr)
    np.save(corners_npy, corners)
    write_json(
        metadata_path,
        {
            "sample_id": sample_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "lens": config["camera"]["lens"],
            "image": str(raw_path),
            "debug_image": str(debug_path),
            "corners_npy": corners_npy.name,
            "image_size": {"width": int(image_bgr.shape[1]), "height": int(image_bgr.shape[0])},
            "blur_score": decision.blur_score,
            "coverage_ratio": decision.coverage_ratio,
            "board_center": None if decision.board_center is None else list(decision.board_center),
            "board_bbox": None if decision.board_bbox is None else list(decision.board_bbox),
            "board_area": decision.board_area_ratio,
            "pose_delta": decision.pose_delta,
            "center_shift": decision.nearest_center_shift,
            "area_change": decision.nearest_area_change,
            "accept_reason": decision.reason,
            "detection": detection.debug_info,
            "config": config,
        },
    )


def run_capture_session(session_dir: Path, config: dict[str, Any]) -> CaptureSessionResult:
    """Run automatic calibration capture with optional manual overrides."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python is required for calibration capture.") from exc

    dirs = ensure_session_dirs(session_dir)
    camera = create_camera_source(config["camera"])
    camera.start()

    previous_signatures: list[np.ndarray] = []
    sample_count = len(list(dirs["samples"].glob("sample_*_metadata.json")))
    last_saved_s = 0.0
    min_samples = int(config["capture"].get("min_samples", 30))
    max_samples = int(config["capture"].get("max_samples", 80))
    min_interval = float(config["capture"].get("min_time_between_samples_s", 0.8))
    auto_calibrate = bool(config["capture"].get("auto_calibrate_when_enough_samples", True))
    auto_delay_s = float(config["capture"].get("auto_calibrate_delay_s", 3.0))
    min_reached_at_s: float | None = None
    force_save = False
    stopped_reason = "quit"

    print(
        "[calibration_capture] Automatic sampling started. "
        "Move board: center, top-left, top-right, bottom-left, bottom-right, closer, farther, tilt, rotate."
    )
    try:
        while sample_count < max_samples:
            frame = camera.read()
            detection = detect_board(frame, config["calibration_board"])
            decision, signature = evaluate_sample_quality(
                image_bgr=frame,
                detected=detection.detected,
                corners=detection.corners,
                capture_config=config["capture"],
                previous_signatures=previous_signatures,
                force_accept=force_save,
            )

            now_s = time.monotonic()
            seconds_until_next = max(0.0, min_interval - (now_s - last_saved_s))
            enough_time = seconds_until_next <= 0.0
            if decision.accept and not enough_time and not force_save:
                decision = QualityDecision(
                    False,
                    "waiting for sample interval",
                    decision.blur_score,
                    decision.coverage_ratio,
                    decision.pose_delta,
                    decision.board_center,
                    decision.board_bbox,
                    decision.board_area_ratio,
                    decision.nearest_center_shift,
                    decision.nearest_area_change,
                )
            should_save = detection.detected and decision.accept and (enough_time or force_save) and detection.corners is not None
            debug = draw_chessboard_debug(frame, config["calibration_board"], detection)
            guide = next_view_guide(previous_signatures)
            auto_calibrate_countdown = None
            if auto_calibrate and sample_count >= min_samples and min_reached_at_s is not None:
                auto_calibrate_countdown = max(0.0, auto_delay_s - (now_s - min_reached_at_s))
            _draw_capture_hud(
                debug,
                config,
                sample_count,
                decision,
                detection.detected,
                seconds_until_next=seconds_until_next,
                guide=guide,
                auto_calibrate_countdown=auto_calibrate_countdown,
            )

            if should_save:
                save_sample(
                    dirs=dirs,
                    sample_index=sample_count,
                    image_bgr=frame,
                    debug_bgr=debug,
                    corners=detection.corners,
                    detection=detection,
                    decision=decision,
                    config=config,
                )
                sample_count += 1
                last_saved_s = now_s
                force_save = False
                if signature is not None:
                    previous_signatures.append(signature)
                print(f"[calibration_capture] AUTO SAVE sample={sample_count} reason={decision.reason}")
                if sample_count >= min_samples:
                    first_min_reached = min_reached_at_s is None
                    min_reached_at_s = time.monotonic()
                else:
                    first_min_reached = False
                if first_min_reached:
                    print(
                        f"[calibration_capture] min_samples reached ({sample_count}/{min_samples}). "
                        f"Auto calibration will start after {auto_delay_s:.1f}s without a new accepted sample."
                    )

            if sample_count >= max_samples:
                stopped_reason = "max_samples_reached"
                break

            if auto_calibrate and sample_count >= min_samples and min_reached_at_s is not None:
                if (time.monotonic() - min_reached_at_s) >= auto_delay_s:
                    stopped_reason = "auto_calibrate_min_samples"
                    break

            cv2.imshow("Hik Camera Calibration", debug)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27):
                stopped_reason = "user_quit"
                break
            if key in (ord("s"), ord("S")):
                force_save = True
                print("[calibration_capture] Manual force-save requested for next detected frame.")
            if key in (ord("r"), ord("R")):
                previous_signatures.clear()
                sample_count = len(list(dirs["samples"].glob("sample_*_metadata.json")))
                min_reached_at_s = time.monotonic() if sample_count >= min_samples else None
                force_save = False
                print("[calibration_capture] Reset in-memory diversity guide for this session.")
            if key in (ord("c"), ord("C")) and sample_count >= min_samples:
                stopped_reason = "user_calibrate_now"
                break

        if sample_count >= max_samples:
            stopped_reason = "max_samples_reached"
        should_calibrate = sample_count >= min_samples and stopped_reason != "user_quit"
        return CaptureSessionResult(
            session_dir=session_dir,
            saved_samples=sample_count,
            should_calibrate=should_calibrate,
            stopped_reason=stopped_reason,
        )
    finally:
        camera.stop()
        cv2.destroyAllWindows()


def next_view_guide(previous_signatures: list[np.ndarray]) -> str:
    """Suggest the next board placement from saved center/scale distribution."""
    if not previous_signatures:
        return "Move board to image center"
    centers = np.array([sig[0:2] for sig in previous_signatures], dtype=np.float64)
    scales = np.array([sig[2] for sig in previous_signatures], dtype=np.float64)
    targets = [
        ("Move board to image center", np.array([0.5, 0.5])),
        ("Move board to top-left", np.array([0.25, 0.25])),
        ("Move board to top-right", np.array([0.75, 0.25])),
        ("Move board to bottom-left", np.array([0.25, 0.75])),
        ("Move board to bottom-right", np.array([0.75, 0.75])),
    ]
    covered = {label: bool(np.any(np.linalg.norm(centers - target, axis=1) < 0.18)) for label, target in targets}
    for label, _target in targets:
        if not covered[label]:
            return label
    if np.max(scales) - np.min(scales) < 0.18:
        return "Move board closer or farther"
    return "Tilt or rotate the board"


def _draw_capture_hud(
    canvas: np.ndarray,
    config: dict[str, Any],
    sample_count: int,
    decision: QualityDecision,
    detected: bool,
    *,
    seconds_until_next: float,
    guide: str,
    auto_calibrate_countdown: float | None,
) -> None:
    """Draw live capture status text."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python is required for calibration HUD drawing.") from exc

    min_samples = int(config["capture"].get("min_samples", 30))
    max_samples = int(config["capture"].get("max_samples", 80))
    decision_text = "ACCEPT" if decision.accept else "REJECT"
    countdown_text = "ready" if seconds_until_next <= 0.0 else f"{seconds_until_next:.1f}s"
    auto_text = "off" if auto_calibrate_countdown is None else f"{auto_calibrate_countdown:.1f}s"
    lines = [
        f"lens: {config['camera']['lens']}",
        f"saved samples: {sample_count} / {min_samples} / {max_samples}",
        f"board detected: {'yes' if detected else 'no'}",
        f"blur_score: {decision.blur_score:.1f}",
        f"coverage_ratio: {decision.coverage_ratio:.3f}",
        f"current decision: {decision_text}",
        f"reject reason: {'' if decision.accept else decision.reason}",
        f"sample interval: {countdown_text}",
        f"auto calibrate countdown: {auto_text}",
        f"guide: {guide}",
        "q: quit | c: calibrate now | r: reset session | s: force save current frame",
    ]
    x, y = 20, 30
    for line in lines:
        cv2.putText(canvas, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 255), 2, cv2.LINE_AA)
        y += 30
