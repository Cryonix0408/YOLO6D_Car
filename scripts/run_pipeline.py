"""运行实时 / 回放 6DoF 推理流水线的脚本入口。"""

from pathlib import Path
import sys

# 约定将项目根目录下的 src 加入模块搜索路径，方便直接运行本脚本。
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yolo6d_car.pipeline import main


if __name__ == "__main__":
    main()
