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
# 检测 Windows Conda 安装：C:\Users\31130\helios\Lib\site-packages\pyhelios\bin\helios++.exe
HELIOS_PATH = os.getenv("HELIOS_PATH", r"C:\Users\31130\helios\Lib\site-packages\pyhelios\bin\helios++.exe")

# HELIOS++ 资源路径（Conda 安装：pyhelios 包目录）
_HELIOS_REPO = Path(os.getenv("HELIOS_REPO", r"C:\Users\31130\helios\Lib\site-packages\pyhelios"))

# HELIOS++ Conda 环境根目录
_HELIOS_CONDA = Path(os.getenv("HELIOS_CONDA", r"C:\Users\31130\helios"))

# 确保 HELIOS++ 的 DLL 依赖在 PATH 中（Windows Conda 环境需要）
def _setup_helios_path() -> None:
    """将 HELIOS++ Conda 环境的 bin 目录添加到 PATH，确保 DLL 可以找到。"""
    if os.name == 'nt':  # Windows only
        helios_bin_dirs = [
            str(_HELIOS_CONDA),
            str(_HELIOS_CONDA / "Library" / "bin"),
            str(_HELIOS_CONDA / "Library" / "usr" / "bin"),
            str(_HELIOS_CONDA / "Scripts"),
        ]
        current_path = os.environ.get("PATH", "")
        new_paths = [p for p in helios_bin_dirs if p not in current_path and os.path.exists(p)]
        if new_paths:
            os.environ["PATH"] = ";".join(new_paths) + ";" + current_path

# 启动时设置 PATH
_setup_helios_path()

# HELIOS++ --assets 搜索路径：
#   - pyhelios 数据目录：解析 data/sceneparts、data/scenes、data/platforms.xml 等
_DEFAULT_ASSETS = [
    str(_HELIOS_REPO),
]
HELIOS_ASSETS = [
    p for p in os.getenv("HELIOS_ASSETS", os.pathsep.join(_DEFAULT_ASSETS)).split(os.pathsep) if p
]

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
