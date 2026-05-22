"""训练 Ultralytics Pose 模型的命令行入口。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    """定义训练入口参数；训练超参尽量暴露为命令行覆盖项。"""
    parser = argparse.ArgumentParser(description="Train an Ultralytics pose model on the prepared car dataset.")
    parser.add_argument("--dataset", required=True, help="Path to dataset.yaml prepared for Ultralytics pose.")
    parser.add_argument("--model", required=True, help="Ultralytics pose checkpoint or model YAML.")
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


def main() -> None:
    """检查数据集路径，组装 Ultralytics train 参数，并打印本次训练摘要。"""
    args = parse_args()

    dataset_path = Path(args.dataset).resolve()
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset YAML not found: {dataset_path}")

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
        "project": str(Path(args.project).resolve()),
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
    model = YOLO(args.model)
    results = model.train(**train_kwargs)

    # 训练结束后打印最小摘要，方便日志系统或人工复制记录。
    summary = {
        "dataset": str(dataset_path),
        "model": args.model,
        "project": str(Path(args.project).resolve()),
        "name": args.name,
        "save_dir": str(Path(getattr(results, "save_dir", Path(args.project) / args.name)).resolve()),
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

