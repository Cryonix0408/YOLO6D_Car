r"""手动或自动采集小车目标图像。

自动模式通过统一相机工厂支持 D455、Hikrobot 和 Webcam，并根据清晰度、场景变化
和稳定帧数量避免重复保存同一位置。采集笔记本应配合
``configs\paths_laptop.yaml`` 使用，输出通常位于
``D:\CaptureData\<date>\<session_name>``。实际输出根目录始终以传入的路径配置为准。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

try:
    import cv2
except ImportError as exc:
    raise RuntimeError("opencv-python is required to run object capture.") from exc

from capture_board_samples import (  # noqa: E402
    _draw_overlay,
    _ensure_dirs,
    _next_sample_index,
    _open_manifest,
    _save_frame,
    _save_intrinsics,
    _save_session_info,
)
from yolo6d_car.camera.d455 import D455Stream  # noqa: E402
from yolo6d_car.camera.factory import create_camera, validate_camera_config  # noqa: E402
from yolo6d_car.config import CameraConfig, load_config  # noqa: E402
from yolo6d_car.path_utils import load_local_paths, resolve_path  # noqa: E402
from yolo6d_car.types import CameraIntrinsics, ImageFrame  # noqa: E402


@dataclass(slots=True)
class AutoCaptureConfig:
    """Resolved auto-capture configuration."""

    camera: dict[str, Any]
    capture: dict[str, Any]
    output: dict[str, Any]
    mocap: dict[str, Any]


@dataclass(slots=True)
class AutoDecision:
    """Per-frame auto-capture decision."""

    decision: str
    reject_reason: str
    blur_score: float
    frame_difference_score: float
    scene_change_score: float
    stable_frame_count: int
    waiting_for_scene_change: bool


@dataclass(slots=True)
class AutoCaptureState:
    """Mutable state for automatic capture."""

    saved_count: int = 0
    stable_frame_count: int = 0
    last_saved_gray: np.ndarray | None = None
    last_saved_time_s: float | None = None
    last_saved_wall_time: str | None = None
    waiting_for_scene_change: bool = False
    paused: bool = False
    recent_gray: deque[np.ndarray] = field(default_factory=lambda: deque(maxlen=8))
    last_reject_reason: str = "startup"


class SyntheticFrameSource:
    """Small synthetic frame source for no-camera dry-run testing."""

    def __init__(self, width: int, height: int, fps: int) -> None:
        self.width = width
        self.height = height
        self.fps = max(int(fps), 1)
        self.index = 0
        self.intrinsics = CameraIntrinsics(
            fx=900.0,
            fy=900.0,
            cx=width / 2.0,
            cy=height / 2.0,
            width=width,
            height=height,
            dist_coeffs=np.zeros(5, dtype=np.float64),
        )

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def wait_for_frame(self) -> ImageFrame:
        block = self.index // 7
        x = 80 + (block % 5) * 90
        y = 90 + (block % 3) * 70
        image = np.full((self.height, self.width, 3), 38, dtype=np.uint8)
        cv2.rectangle(image, (x, y), (x + 180, y + 90), (40 + block * 20 % 180, 190, 70), -1)
        cv2.putText(image, f"dry-run {self.index:03d}", (30, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (240, 240, 240), 2)
        timestamp_s = self.index / self.fps
        self.index += 1
        return ImageFrame(color=image, depth=None, timestamp_s=timestamp_s, intrinsics=self.intrinsics)


class WebcamFrameSource:
    """OpenCV webcam source with the same minimal interface as D455Stream."""

    def __init__(self, width: int, height: int, fps: int, index: int = 0) -> None:
        self.width = width
        self.height = height
        self.fps = fps
        self.index = index
        self.capture = None
        self.intrinsics = CameraIntrinsics(
            fx=900.0,
            fy=900.0,
            cx=width / 2.0,
            cy=height / 2.0,
            width=width,
            height=height,
            dist_coeffs=np.zeros(5, dtype=np.float64),
        )

    def start(self) -> None:
        self.capture = cv2.VideoCapture(self.index)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.capture.set(cv2.CAP_PROP_FPS, self.fps)
        if not self.capture.isOpened():
            raise RuntimeError("OpenCV webcam not opened")

    def stop(self) -> None:
        if self.capture is not None:
            self.capture.release()
            self.capture = None

    def wait_for_frame(self) -> ImageFrame:
        if self.capture is None:
            raise RuntimeError("Webcam source must be started before reading frames.")
        ok, color = self.capture.read()
        if not ok or color is None:
            raise RuntimeError("OpenCV webcam did not return a frame")
        return ImageFrame(color=color, depth=None, timestamp_s=time.time(), intrinsics=self.intrinsics)


def parse_args() -> argparse.Namespace:
    """Define manual and automatic object capture arguments."""
    parser = argparse.ArgumentParser(description="Capture car/object samples.")
    parser.add_argument("--config", required=True, help="Path to capture YAML config.")
    parser.add_argument("--paths-config", default=None, help="Optional local paths YAML, e.g. configs/paths_local.yaml.")
    parser.add_argument("--validate-config", action="store_true", help="Validate config and paths without opening the camera.")
    parser.add_argument("--dry-run", action="store_true", help="Run auto-capture logic with synthetic frames and no image saving.")
    parser.add_argument("--max-frames", type=int, default=None, help="Maximum frames to process, useful for dry-run.")
    parser.add_argument("--overwrite", action="store_true", help="Allow reusing an existing auto-capture session directory.")
    parser.add_argument("--output-dir", default=None, help="Override output directory.")
    parser.add_argument("--prefix", default="car", help="Filename prefix for legacy manual mode.")
    parser.add_argument("--save-depth", action="store_true", help="Save aligned depth PNG files in legacy manual mode.")
    parser.add_argument("--warmup-frames", type=int, default=20, help="Initial frames to discard in legacy manual mode.")
    return parser.parse_args()


def load_auto_config(config_path: str | Path) -> AutoCaptureConfig:
    """Load auto-capture YAML."""
    path = Path(config_path).resolve()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return AutoCaptureConfig(
        camera=dict(raw.get("camera", {})),
        capture=dict(raw.get("capture", {})),
        output=dict(raw.get("output", {})),
        mocap=dict(raw.get("mocap", {})),
    )


def is_auto_config(config_path: str | Path) -> bool:
    """Return true if YAML requests auto-capture mode."""
    raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    capture = raw.get("capture", {})
    return isinstance(capture, dict) and str(capture.get("mode", "")).lower() == "auto"


def validate_auto_config(config: AutoCaptureConfig) -> list[str]:
    """Validate required auto-capture fields and return non-fatal warnings."""
    required_camera = ("source", "width", "height", "fps", "enable_depth", "align_depth_to_color")
    required_capture = (
        "mode",
        "session_name",
        "object_name",
        "target_samples",
        "min_time_between_samples_s",
        "stable_frames_required",
        "blur_threshold",
        "frame_difference_threshold",
        "min_scene_change_score",
        "save_rgb",
        "save_depth",
        "save_preview",
        "save_metadata",
        "auto_stop_when_target_reached",
    )
    required_output = ("root", "date_format")
    missing = [f"camera.{key}" for key in required_camera if key not in config.camera]
    missing.extend(f"capture.{key}" for key in required_capture if key not in config.capture)
    missing.extend(f"output.{key}" for key in required_output if key not in config.output)
    if missing:
        raise ValueError(f"Auto object capture config missing required fields: {missing}")
    warnings: list[str] = []
    if str(config.camera["source"]).lower() not in {"d455", "hikrobot", "webcam"}:
        raise ValueError("camera.source must be one of: d455, hikrobot, webcam")
    if int(config.capture["target_samples"]) <= 0:
        raise ValueError("capture.target_samples must be > 0")
    warnings.extend(validate_camera_config(config.camera))
    return warnings


def resolve_auto_output_dir(config: AutoCaptureConfig, args: argparse.Namespace) -> Path:
    """Resolve auto-capture session directory under the configured data root."""
    if args.output_dir:
        local_paths = load_local_paths(args.paths_config) if args.paths_config else None
        output = resolve_path(args.output_dir, project_root=ROOT, local_paths=local_paths)
        if output is None:
            raise ValueError("--output-dir could not be resolved.")
        return output.resolve()
    date_text = datetime.now().strftime(str(config.output.get("date_format", "%Y-%m-%d")))
    root_raw = str(config.output.get("root", "captures"))
    local_paths = load_local_paths(args.paths_config) if args.paths_config else None
    root_path = resolve_path(root_raw, project_root=ROOT, local_paths=local_paths)
    if root_path is None:
        raise ValueError("output.root could not be resolved.")
    return (root_path / date_text / str(config.capture["session_name"])).resolve()


def validate_object_capture_config(args: argparse.Namespace) -> None:
    """Validate config without opening a real camera."""
    config_path = Path(args.config).resolve()
    if is_auto_config(config_path):
        config = load_auto_config(config_path)
        warnings = validate_auto_config(config)
        output_dir = resolve_auto_output_dir(config, args)
        payload = {
            "status": "ok",
            "mode": "auto",
            "script": Path(__file__).name,
            "config": str(config_path),
            "paths_config": None if args.paths_config is None else str(Path(args.paths_config).resolve()),
            "camera": config.camera,
            "capture": {
                "session_name": config.capture["session_name"],
                "target_samples": config.capture["target_samples"],
                "object_name": config.capture["object_name"],
            },
            "output_dir": str(output_dir),
            "output_parent_exists": output_dir.parent.exists(),
            "opencv_available": cv2 is not None,
            "hardware_required": False,
            "warnings": warnings,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return None

    project_config = load_config(config_path, paths_config=args.paths_config)
    output_dir = Path(args.output_dir).resolve() if args.output_dir else _default_output_dir(args.paths_config)
    print(
        json.dumps(
            {
                "status": "ok",
                "mode": "manual_legacy",
                "script": Path(__file__).name,
                "config": str(config_path),
                "paths_config": None if args.paths_config is None else str(Path(args.paths_config).resolve()),
                "camera": {
                    "source": project_config.camera.source,
                    "width": project_config.camera.color_width,
                    "height": project_config.camera.color_height,
                    "fps": project_config.camera.fps,
                    "enable_depth": project_config.camera.enable_depth,
                },
                "output_dir": str(output_dir),
                "output_parent_exists": output_dir.parent.exists(),
                "hardware_required": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _default_output_dir(paths_config: str | None = None) -> Path:
    """Legacy default output directory."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if paths_config:
        return load_local_paths(paths_config).outputs_root / "object_capture" / timestamp
    return ROOT / "outputs" / "object_capture" / timestamp


def blur_score(image_bgr: np.ndarray) -> float:
    """Compute Laplacian variance blur score."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def gray_frame(image_bgr: np.ndarray) -> np.ndarray:
    """Convert image to grayscale float32 for difference scoring."""
    return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)


def frame_difference(current_gray: np.ndarray, reference_gray: np.ndarray | None) -> tuple[float, float]:
    """Return mean absolute diff and normalized scene change score."""
    if reference_gray is None:
        return 1e9, 1.0
    current = current_gray
    reference = reference_gray
    if current.shape != reference.shape:
        reference = cv2.resize(reference, (current.shape[1], current.shape[0]))
    diff = float(np.mean(np.abs(current - reference)))
    return diff, diff / 255.0


def update_stability(state: AutoCaptureState, current_gray: np.ndarray, threshold: float, required: int) -> int:
    """Update stable-frame count from adjacent frame differences."""
    if not state.recent_gray:
        state.stable_frame_count = 0
    else:
        diff, _ = frame_difference(current_gray, state.recent_gray[-1])
        if diff <= threshold:
            state.stable_frame_count += 1
        else:
            state.stable_frame_count = 0
    state.recent_gray.append(current_gray.copy())
    return min(state.stable_frame_count, required)


def decide_auto_capture(frame: ImageFrame, config: AutoCaptureConfig, state: AutoCaptureState, now_s: float) -> AutoDecision:
    """Apply the auto-capture acceptance/rejection rules to one frame."""
    capture = config.capture
    current_gray = gray_frame(frame.color)
    blur = blur_score(frame.color)
    frame_diff, scene_change = frame_difference(current_gray, state.last_saved_gray)
    stable_count = update_stability(
        state,
        current_gray,
        float(capture["frame_difference_threshold"]),
        int(capture["stable_frames_required"]),
    )

    if state.waiting_for_scene_change:
        changed = frame_diff >= float(capture["frame_difference_threshold"]) or scene_change >= float(capture["min_scene_change_score"])
        if changed:
            state.waiting_for_scene_change = False
            state.stable_frame_count = 0
            state.recent_gray.clear()
        else:
            return AutoDecision("WAITING", "too_similar_to_last_saved", blur, frame_diff, scene_change, stable_count, True)

    reject_reason = ""
    if state.paused:
        reject_reason = "paused"
    elif state.saved_count >= int(capture["target_samples"]):
        reject_reason = "target_reached"
    elif state.last_saved_time_s is not None and now_s - state.last_saved_time_s < float(capture["min_time_between_samples_s"]):
        reject_reason = "too_soon"
    elif blur < float(capture["blur_threshold"]):
        reject_reason = "blur_too_low"
    elif stable_count < int(capture["stable_frames_required"]):
        reject_reason = "not_stable"
    elif state.last_saved_gray is not None and frame_diff < float(capture["frame_difference_threshold"]) and scene_change < float(
        capture["min_scene_change_score"]
    ):
        reject_reason = "too_similar_to_last_saved"

    if reject_reason:
        state.last_reject_reason = reject_reason
        decision = "PAUSED" if reject_reason == "paused" else "WAITING" if reject_reason in {"too_soon", "not_stable"} else "REJECT"
        return AutoDecision(decision, reject_reason, blur, frame_diff, scene_change, stable_count, state.waiting_for_scene_change)

    return AutoDecision("ACCEPT", "", blur, frame_diff, scene_change, stable_count, state.waiting_for_scene_change)


def create_auto_dirs(output_dir: Path, save_depth: bool, save_preview: bool, save_metadata: bool, overwrite: bool) -> dict[str, Path | None]:
    """Create auto-capture output directories safely."""
    if output_dir.exists() and any(output_dir.iterdir()) and not overwrite:
        raise FileExistsError(f"Output session already exists and is not empty: {output_dir}. Use --overwrite to append/reuse.")
    output_dir.mkdir(parents=True, exist_ok=True)
    dirs: dict[str, Path | None] = {
        "images": output_dir / "images",
        "depth": output_dir / "depth" if save_depth else None,
        "previews": output_dir / "previews" if save_preview else None,
        "metadata": output_dir / "metadata" if save_metadata else None,
    }
    for path in dirs.values():
        if path is not None:
            path.mkdir(parents=True, exist_ok=True)
    return dirs


def draw_auto_overlay(image: np.ndarray, config: AutoCaptureConfig, state: AutoCaptureState, decision: AutoDecision) -> np.ndarray:
    """Draw auto-capture HUD."""
    canvas = image.copy()
    lines = [
        f"session: {config.capture['session_name']}",
        f"camera: {config.camera['source']}",
        f"saved: {state.saved_count}/{config.capture['target_samples']}",
        f"blur: {decision.blur_score:.1f}",
        f"stable: {decision.stable_frame_count}/{config.capture['stable_frames_required']}",
        f"frame diff: {decision.frame_difference_score:.2f}",
        f"scene change: {decision.scene_change_score:.3f}",
        f"decision: {decision.decision}",
        f"reject: {decision.reject_reason}",
        f"waiting scene change: {state.waiting_for_scene_change}",
        f"last saved: {state.last_saved_wall_time or 'none'}",
        "q: quit  s: force save  p: pause/resume  r: reset counter  h: help",
    ]
    overlay = canvas.copy()
    cv2.rectangle(overlay, (10, 10), (760, 10 + 24 * len(lines) + 12), (20, 20, 20), -1)
    canvas = cv2.addWeighted(overlay, 0.62, canvas, 0.38, 0)
    y = 34
    for line in lines:
        cv2.putText(canvas, line, (22, y), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 2, cv2.LINE_AA)
        y += 24
    return canvas


def save_auto_sample(
    frame: ImageFrame,
    preview: np.ndarray,
    config: AutoCaptureConfig,
    state: AutoCaptureState,
    decision: AutoDecision,
    dirs: dict[str, Path | None],
    output_dir: Path,
    auto_saved: bool,
    save_reason: str,
    index_writer: csv.DictWriter,
) -> None:
    """Save one accepted or force-saved sample."""
    sample_id = state.saved_count + 1
    stem = f"sample_{sample_id:06d}"
    image_rel = f"images/{stem}.png"
    depth_rel = None
    preview_rel = None
    image_path = dirs["images"] / f"{stem}.png"  # type: ignore[operator]
    if bool(config.capture.get("save_rgb", True)):
        if not cv2.imwrite(str(image_path), frame.color):
            raise RuntimeError(f"Failed to save image: {image_path}")
    if dirs["depth"] is not None and frame.depth is not None:
        depth_rel = f"depth/{stem}.npy"
        np.save(dirs["depth"] / f"{stem}.npy", frame.depth)
    if dirs["previews"] is not None:
        preview_rel = f"previews/{stem}_preview.png"
        cv2.imwrite(str(dirs["previews"] / f"{stem}_preview.png"), preview)

    timestamp = datetime.now().isoformat(timespec="milliseconds")
    if dirs["metadata"] is not None:
        metadata = {
            "sample_id": sample_id,
            "timestamp": timestamp,
            "object_name": config.capture["object_name"],
            "camera_source": config.camera["source"],
            "image_path": image_rel,
            "depth_path": depth_rel,
            "preview_path": preview_rel,
            "blur_score": decision.blur_score,
            "frame_difference_score": decision.frame_difference_score,
            "scene_change_score": decision.scene_change_score,
            "stable_frame_count": decision.stable_frame_count,
            "auto_saved": auto_saved,
            "save_reason": save_reason,
            "reject_reason_before_accept": state.last_reject_reason,
            "config_snapshot": {
                "camera": config.camera,
                "capture": config.capture,
                "output": config.output,
                "mocap": config.mocap,
            },
        }
        (dirs["metadata"] / f"{stem}.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    index_writer.writerow(
        {
            "sample_id": sample_id,
            "timestamp": timestamp,
            "image_path": image_rel,
            "depth_path": "" if depth_rel is None else depth_rel,
            "preview_path": "" if preview_rel is None else preview_rel,
            "blur_score": f"{decision.blur_score:.6f}",
            "frame_difference_score": f"{decision.frame_difference_score:.6f}",
            "scene_change_score": f"{decision.scene_change_score:.6f}",
            "stable_frame_count": decision.stable_frame_count,
            "auto_saved": str(auto_saved).lower(),
            "save_reason": save_reason,
        }
    )
    state.saved_count += 1
    state.last_saved_gray = gray_frame(frame.color)
    state.last_saved_time_s = time.monotonic()
    state.last_saved_wall_time = timestamp
    state.waiting_for_scene_change = True
    state.stable_frame_count = 0
    state.recent_gray.clear()
    write_capture_report(output_dir, config, state)


def write_capture_metadata(output_dir: Path, config_path: Path, config: AutoCaptureConfig) -> None:
    """Write session-level metadata."""
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "config_path": str(config_path),
        "session_name": config.capture["session_name"],
        "object_name": config.capture["object_name"],
        "camera": config.camera,
        "capture": config.capture,
        "mocap": config.mocap,
    }
    (output_dir / "capture_metadata.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_capture_report(output_dir: Path, config: AutoCaptureConfig, state: AutoCaptureState) -> None:
    """Write a lightweight capture report."""
    lines = [
        "# Auto Object Capture Report",
        "",
        f"- Session: `{config.capture['session_name']}`",
        f"- Object: `{config.capture['object_name']}`",
        f"- Camera: `{config.camera['source']}`",
        f"- Saved samples: {state.saved_count}/{config.capture['target_samples']}",
        f"- Last saved: {state.last_saved_wall_time or 'none'}",
        "",
        "This report is updated during capture. Final labeling still needs mocap CSV and label generation.",
    ]
    (output_dir / "capture_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_frame_source(config: AutoCaptureConfig, *, dry_run: bool):
    """创建相机或合成帧源。

    真实相机统一交给 camera.factory 创建，自动采集判定与保存逻辑无需关心品牌。
    validate-config 只做结构检查，因此不会依赖真实相机或 SDK 当前在线。
    """
    width = int(config.camera["width"])
    height = int(config.camera["height"])
    fps = int(config.camera["fps"])
    if dry_run:
        return SyntheticFrameSource(width, height, fps)
    return create_camera(config.camera)


def run_auto_capture(args: argparse.Namespace) -> None:
    """Run auto-capture mode."""
    if not args.dry_run and args.paths_config is None:
        raise SystemExit("Auto capture writes large data; pass --paths-config configs\\paths_local.yaml so output resolves to data_root.")
    config_path = Path(args.config).resolve()
    config = load_auto_config(config_path)
    validate_auto_config(config)
    output_dir = resolve_auto_output_dir(config, args)
    state = AutoCaptureState()
    source = build_frame_source(config, dry_run=args.dry_run)

    dirs: dict[str, Path | None] = {"images": None, "depth": None, "previews": None, "metadata": None}
    index_handle = None
    index_writer = None
    if not args.dry_run:
        dirs = create_auto_dirs(
            output_dir,
            save_depth=bool(config.capture.get("save_depth", False)),
            save_preview=bool(config.capture.get("save_preview", True)),
            save_metadata=bool(config.capture.get("save_metadata", True)),
            overwrite=bool(args.overwrite),
        )
        write_capture_metadata(output_dir, config_path, config)
        write_capture_report(output_dir, config, state)
        index_handle = (output_dir / "capture_index.csv").open("a", encoding="utf-8", newline="")
        index_writer = csv.DictWriter(
            index_handle,
            fieldnames=[
                "sample_id",
                "timestamp",
                "image_path",
                "depth_path",
                "preview_path",
                "blur_score",
                "frame_difference_score",
                "scene_change_score",
                "stable_frame_count",
                "auto_saved",
                "save_reason",
            ],
        )
        if index_handle.tell() == 0:
            index_writer.writeheader()

    source.start()
    frame_count = 0
    try:
        while args.max_frames is None or frame_count < args.max_frames:
            frame = source.wait_for_frame()
            now_s = time.monotonic()
            decision = decide_auto_capture(frame, config, state, now_s)
            preview = draw_auto_overlay(frame.color, config, state, decision)

            if args.dry_run:
                if decision.decision == "ACCEPT":
                    state.saved_count += 1
                    state.last_saved_gray = gray_frame(frame.color)
                    state.last_saved_time_s = now_s
                    state.last_saved_wall_time = datetime.now().isoformat(timespec="milliseconds")
                    state.waiting_for_scene_change = True
                print(
                    json.dumps(
                        {
                            "frame": frame_count,
                            "decision": decision.decision,
                            "reject_reason": decision.reject_reason,
                            "saved_count": state.saved_count,
                            "blur_score": decision.blur_score,
                            "frame_difference_score": decision.frame_difference_score,
                            "scene_change_score": decision.scene_change_score,
                            "stable_frame_count": decision.stable_frame_count,
                            "waiting_for_scene_change": state.waiting_for_scene_change,
                        },
                        ensure_ascii=False,
                    )
                )
            else:
                cv2.imshow("Auto Object Capture", preview)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q"), ord("Q")):
                    break
                if key in (ord("p"), ord("P")):
                    state.paused = not state.paused
                elif key in (ord("h"), ord("H")):
                    print("q: quit, s: force save, p: pause/resume, r: reset counter, h: help")
                elif key in (ord("r"), ord("R")):
                    state.saved_count = 0
                    state.stable_frame_count = 0
                    state.waiting_for_scene_change = False
                    state.recent_gray.clear()
                    print("Session counter/state reset in memory; existing files were not deleted.")
                elif key in (ord("s"), ord("S")) and index_writer is not None:
                    save_auto_sample(frame, preview, config, state, decision, dirs, output_dir, False, "force_save", index_writer)

                if decision.decision == "ACCEPT" and index_writer is not None:
                    save_auto_sample(frame, preview, config, state, decision, dirs, output_dir, True, "auto_accept", index_writer)
                    print(json.dumps({"saved": state.saved_count, "output_dir": str(output_dir)}, ensure_ascii=False))

            frame_count += 1
            if bool(config.capture.get("auto_stop_when_target_reached", True)) and state.saved_count >= int(config.capture["target_samples"]):
                break
    finally:
        source.stop()
        if index_handle is not None:
            index_handle.close()
        if not args.dry_run:
            cv2.destroyAllWindows()


def run_manual_legacy(args: argparse.Namespace) -> None:
    """Run the original manual D455 capture mode."""
    config_path = Path(args.config).resolve()
    config = load_config(config_path, paths_config=args.paths_config)
    output_dir = Path(args.output_dir).resolve() if args.output_dir else _default_output_dir(args.paths_config)
    images_dir, depth_dir = _ensure_dirs(output_dir, save_depth=args.save_depth)
    manifest_writer, manifest_handle = _open_manifest(output_dir)
    stream = D455Stream(config.camera)
    stream.start()

    try:
        for _ in range(max(args.warmup_frames, 0)):
            stream.wait_for_frame()
        frame = stream.wait_for_frame()
        _save_intrinsics(output_dir, frame.intrinsics)
        _save_session_info(output_dir, config_path=config_path, save_depth=args.save_depth)
        sample_index = _next_sample_index(images_dir=images_dir, prefix=args.prefix)
        saved_count = sample_index
        while True:
            frame = stream.wait_for_frame()
            preview = ImageFrame(color=frame.color.copy(), depth=frame.depth, timestamp_s=frame.timestamp_s, intrinsics=frame.intrinsics)
            _draw_overlay(preview, sample_count=saved_count, output_dir=output_dir)
            cv2.imshow("D455 Object Capture", preview.color)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q"), ord("Q")):
                break
            if key in (ord(" "), ord("s"), ord("S")):
                image_path, depth_path = _save_frame(
                    frame=frame,
                    sample_index=sample_index,
                    prefix=args.prefix,
                    images_dir=images_dir,
                    depth_dir=depth_dir,
                    manifest=manifest_writer,
                )
                print(
                    json.dumps(
                        {
                            "sample_index": sample_index,
                            "image_path": str(image_path),
                            "depth_path": None if depth_path is None else str(depth_path),
                            "device_timestamp_s": frame.timestamp_s,
                        },
                        ensure_ascii=False,
                    )
                )
                sample_index += 1
                saved_count += 1
    finally:
        manifest_handle.close()
        stream.stop()
        cv2.destroyAllWindows()


def main() -> None:
    """Dispatch manual legacy mode or new auto-capture mode."""
    args = parse_args()
    if args.validate_config:
        validate_object_capture_config(args)
        return None
    if is_auto_config(args.config):
        run_auto_capture(args)
    else:
        if args.dry_run:
            raise SystemExit("--dry-run is supported only for capture.mode=auto configs.")
        run_manual_legacy(args)


if __name__ == "__main__":
    main()
