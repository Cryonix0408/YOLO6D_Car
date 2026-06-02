"""训练 Ultralytics Pose 模型的命令行入口。"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.path_utils import load_local_paths, resolve_path


def parse_args() -> argparse.Namespace:
    """定义训练入口参数；训练超参尽量暴露为命令行覆盖项。"""
    parser = argparse.ArgumentParser(description="Train an Ultralytics pose model on the prepared car dataset.")
    parser.add_argument("--paths-config", default=None, help="Optional local paths YAML, e.g. configs/paths_local.yaml.")
    parser.add_argument("--validate-config", action="store_true", help="Validate training paths and imports without starting training.")
    parser.add_argument("--dataset", default=None, help="Path to dataset.yaml prepared for Ultralytics pose.")
    parser.add_argument("--model", default=None, help="Ultralytics pose checkpoint or model YAML.")
    parser.add_argument("--epochs", type=int, default=150, help="Number of training epochs.")
    parser.add_argument("--imgsz", type=int, default=640, help="Training image size.")
    parser.add_argument("--batch", type=int, default=16, help="Batch size.")
    parser.add_argument("--device", default="", help="Training device, for example 0, cpu, or empty for auto.")
    parser.add_argument("--workers", type=int, default=4, help="Number of dataloader workers.")
    parser.add_argument("--patience", type=int, default=50, help="Early stopping patience.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--project", default=str(Path("outputs") / "train_runs"), help="Training project directory.")
    parser.add_argument("--name", default="custom_model_12pt_pose", help="Run name under the project directory.")
    parser.add_argument("--exist-ok", action="store_true", help="Allow reusing an existing run directory.")
    parser.add_argument("--lr0", type=float, default=None, help="Optional initial learning rate override.")
    parser.add_argument("--degrees", type=float, default=0.0, help="Rotation augmentation in degrees.")
    parser.add_argument("--translate", type=float, default=0.05, help="Translation augmentation factor.")
    parser.add_argument("--scale", type=float, default=0.2, help="Scale augmentation factor.")
    parser.add_argument("--fliplr", type=float, default=0.0, help="Left-right flip probability.")
    parser.add_argument("--mosaic", type=float, default=0.0, help="Mosaic probability.")
    parser.add_argument("--resume", action="store_true", help="Resume an interrupted Ultralytics run.")
    return parser.parse_args()


def validate_train_config(args: argparse.Namespace) -> None:
    """Validate training CLI configuration without loading data or starting training."""
    local_paths = load_local_paths(args.paths_config) if args.paths_config else None
    dataset_path = resolve_path(args.dataset, project_root=ROOT, local_paths=local_paths).resolve() if args.dataset else None
    project_path = resolve_path(args.project, project_root=ROOT, local_paths=local_paths).resolve()
    model_arg = _resolve_model_arg(args.model, local_paths) if args.model else None
    previous_yolo_config_dir = os.environ.get("YOLO_CONFIG_DIR")
    try:
        with tempfile.TemporaryDirectory(prefix="yolo6d_ultralytics_") as tmp_dir:
            os.environ["YOLO_CONFIG_DIR"] = tmp_dir
            try:
                import ultralytics

                ultralytics_status = f"ok {getattr(ultralytics, '__version__', 'unknown')}"
            except Exception as exc:
                ultralytics_status = f"unavailable: {exc}"
    finally:
        if previous_yolo_config_dir is None:
            os.environ.pop("YOLO_CONFIG_DIR", None)
        else:
            os.environ["YOLO_CONFIG_DIR"] = previous_yolo_config_dir
    print(
        json.dumps(
            {
                "status": "ok",
                "script": Path(__file__).name,
                "paths_config": None if args.paths_config is None else str(Path(args.paths_config).resolve()),
                "dataset": None if dataset_path is None else str(dataset_path),
                "dataset_exists": None if dataset_path is None else dataset_path.exists(),
                "model": model_arg,
                "project": str(project_path),
                "project_parent_exists": project_path.parent.exists(),
                "ultralytics": ultralytics_status,
                "large_data_required": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _resolve_model_arg(raw_model: str, local_paths) -> str:
    """Resolve local checkpoint paths while preserving Ultralytics model names."""
    if any(sep in raw_model for sep in ("/", "\\")) or raw_model.startswith(("outputs", "models")):
        resolved = resolve_path(raw_model, project_root=ROOT, local_paths=local_paths)
        return str(resolved.resolve()) if resolved is not None else raw_model
    return raw_model


def main() -> None:
    """检查数据集路径，组装 Ultralytics train 参数，并打印本次训练摘要。"""
    args = parse_args()
    if args.validate_config:
        validate_train_config(args)
        return None
    if not args.dataset or not args.model:
        raise SystemExit("--dataset and --model are required unless --validate-config is used")
    local_paths = load_local_paths(args.paths_config) if args.paths_config else None

    dataset_path = resolve_path(args.dataset, project_root=ROOT, local_paths=local_paths).resolve()
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset YAML not found: {dataset_path}")
    project_path = Path(args.project).resolve()
    if args.paths_config and args.project == str(Path("outputs") / "train_runs"):
        project_path = local_paths.outputs_root / "train_runs"
    elif args.project:
        project_path = resolve_path(args.project, project_root=ROOT, local_paths=local_paths).resolve()
    model_arg = _resolve_model_arg(args.model, local_paths)

    # 延迟导入 Ultralytics，让 --help 在未安装依赖时也能正常显示。
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit(
            "Ultralytics is not installed in the current Python environment.\n"
            "Install it first, for example:\n"
            "  python -m pip install ultralytics\n"
        ) from exc

    # 保持 train_kwargs 和命令行参数一一对应，便于从 args.yaml 反查训练配置。
    train_kwargs = {
        "task": "pose",
        "data": str(dataset_path),
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "device": args.device,
        "workers": args.workers,
        "patience": args.patience,
        "seed": args.seed,
        "project": str(project_path),
        "name": args.name,
        "exist_ok": args.exist_ok,
        "degrees": args.degrees,
        "translate": args.translate,
        "scale": args.scale,
        "fliplr": args.fliplr,
        "mosaic": args.mosaic,
        "plots": True,
    }
    if args.resume:
        train_kwargs["resume"] = True
    if args.lr0 is not None:
        train_kwargs["lr0"] = args.lr0

    # args.model 可以是官方初始权重，也可以是上一轮 best.pt。
    model = YOLO(model_arg)
    results = model.train(**train_kwargs)

    # 训练结束后打印最小摘要，方便日志系统或人工复制记录。
    summary = {
        "dataset": str(dataset_path),
        "model": model_arg,
        "project": str(project_path),
        "name": args.name,
        "save_dir": str(Path(getattr(results, "save_dir", Path(args.project) / args.name)).resolve()),
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
