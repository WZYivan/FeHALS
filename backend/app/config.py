"""全局配置：服务地址、静态目录、HELIOS++ 可执行文件与资源路径。

以 Linux 环境为默认基准（参考 config1.py），所有可调项均支持通过环境变量覆盖；
Windows 平台无需改动本文件，由 run.bat 在启动时注入对应环境变量。
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

# HELIOS++ 可执行文件路径（Linux 默认：helios++ 位于 PATH 中；Windows 由 run.bat 覆盖）
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

# Windows Conda 环境根目录（仅 Windows 需要，由 run.bat 注入；Linux 不设置则跳过）
_HELIOS_CONDA = os.getenv("HELIOS_CONDA", "")


def _setup_helios_path() -> None:
    """Windows 下将 HELIOS++ Conda 环境的 bin 目录加入 PATH，确保 DLL 可以找到。"""
    if os.name != "nt" or not _HELIOS_CONDA:
        return
    helios_bin_dirs = [
        _HELIOS_CONDA,
        os.path.join(_HELIOS_CONDA, "Library", "bin"),
        os.path.join(_HELIOS_CONDA, "Library", "usr", "bin"),
        os.path.join(_HELIOS_CONDA, "Scripts"),
    ]
    current_path = os.environ.get("PATH", "")
    new_paths = [p for p in helios_bin_dirs if p not in current_path and os.path.exists(p)]
    if new_paths:
        os.environ["PATH"] = os.pathsep.join(new_paths) + os.pathsep + current_path


# 启动时设置 PATH（Linux / 未注入 HELIOS_CONDA 时为空操作）
_setup_helios_path()

# 仿真超时时间（秒）
SIMULATION_TIMEOUT = int(os.getenv("FEHALS_SIM_TIMEOUT", "300"))

# 最大并发仿真数（1 = 严格顺序执行；>1 = 并发调度）
MAX_CONCURRENT_SIMULATIONS = int(os.getenv("FEHALS_MAX_CONCURRENT", "1"))

# CORS 允许来源（开发环境放开）
CORS_ORIGINS = [o for o in os.getenv("FEHALS_CORS_ORIGINS", "*").split(",") if o]


def ensure_dirs() -> None:
    """确保静态子目录存在。"""
    for d in (MODELS_DIR, TRAJECTORIES_DIR, CONFIGS_DIR, RESULTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
