"""全局配置：服务地址、静态目录、HELIOS++ 可执行文件与资源路径。

所有可调项均支持通过环境变量覆盖，便于在不同部署环境间切换。
"""
import os
from pathlib import Path

# 服务监听地址与端口
HOST = os.getenv("FEHALS_HOST", "0.0.0.0")
PORT = int(os.getenv("FEHALS_PORT", "8000"))

# 后端静态文件根目录（模型 / 航迹 / 配置 / 结果）
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
MODELS_DIR = STATIC_DIR / "models"
TRAJECTORIES_DIR = STATIC_DIR / "trajectories"
CONFIGS_DIR = STATIC_DIR / "configs"
RESULTS_DIR = STATIC_DIR / "results"

# HELIOS++ 可执行文件路径（helio++ v2.x）
HELIOS_PATH = os.getenv("HELIOS_PATH", "helios++")

# HELIOS++ 源仓库根目录（含 data/sceneparts、data/scenes 等演示资源）
_HELIOS_REPO = Path(os.getenv("HELIOS_REPO", "/home/azusa/file/project/3rd/helios"))

# HELIOS++ --assets 搜索路径：
#   - 仓库根目录：解析 survey 中的 data/sceneparts、data/scenes 等演示资源
#   - pyhelios 数据目录：解析 data/platforms.xml、data/scanners_*.xml 平台/扫描器目录
_DEFAULT_ASSETS = [
    str(_HELIOS_REPO),
    str(_HELIOS_REPO / "python" / "pyhelios"),
]
HELIOS_ASSETS = [
    p for p in os.getenv("HELIOS_ASSETS", os.pathsep.join(_DEFAULT_ASSETS)).split(os.pathsep) if p
]

# 仿真超时时间（秒）
SIMULATION_TIMEOUT = int(os.getenv("FEHALS_SIM_TIMEOUT", "300"))

# CORS 允许来源（开发环境放开）
CORS_ORIGINS = [o for o in os.getenv("FEHALS_CORS_ORIGINS", "*").split(",") if o]


def ensure_dirs() -> None:
    """确保静态子目录存在。"""
    for d in (MODELS_DIR, TRAJECTORIES_DIR, CONFIGS_DIR, RESULTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
