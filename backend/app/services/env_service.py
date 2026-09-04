"""FeHALS 运行环境检测与诊断服务。

检测项（产品最小可用性）：
  1. Python 运行环境：版本、关键依赖可导入性（后端最小可用性）
  2. 静态工作目录：模型 / 航迹 / 配置 / 结果
  3. HELIOS++ 可执行文件：存在性（外部仿真引擎，仅做存在性检查）
"""
import importlib
import sys
from pathlib import Path
from typing import Any, Optional

from app import config as cfg

def _severity(items: list[dict]) -> str:
    statuses = [i.get("status", "ok") for i in items]
    if "error" in statuses:
        return "error"
    if "warning" in statuses:
        return "warning"
    return "ok"

# ------------------------------------------------------------------ #
#  1. Python 后端环境检测（产品最小可用性）
# ------------------------------------------------------------------ #

# 后端关键依赖列表 —— 缺了就跑不起来
_CRITICAL_DEPS = [
    ("fastapi", "FastAPI 框架"),
    ("uvicorn", "ASGI 服务器"),
    ("numpy", "数值计算"),
    ("laspy", "点云 LAS 读写"),
    ("pydantic", "数据校验"),
    ("yaml", "YAML 配置解析（PyYAML）"),
    ("aiofiles", "异步文件操作"),
]

# 可选依赖 —— 缺了不影响启动但部分功能受限
_OPTIONAL_DEPS = [
    ("lazrs", "LAZ 压缩支持"),
    ("websockets", "WebSocket 支持"),
]

def _check_dep(name: str) -> tuple[bool, Optional[str]]:
    """尝试导入一个模块，返回 (是否成功, 版本或错误信息)。"""
    try:
        mod = importlib.import_module(name)
        version = getattr(mod, "__version__", None)
        return True, version
    except ImportError as e:
        return False, str(e)

def diagnose_python_env() -> dict:
    """检测 Python 运行环境和关键依赖。"""
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    # 关键依赖
    critical = []
    for dep, desc in _CRITICAL_DEPS:
        ok, info = _check_dep(dep)
        critical.append({
            "name": dep,
            "description": desc,
            "installed": ok,
            "version": info if ok else None,
            "error": None if ok else info,
            "status": "ok" if ok else "error",
        })

    # 可选依赖
    optional = []
    for dep, desc in _OPTIONAL_DEPS:
        ok, info = _check_dep(dep)
        optional.append({
            "name": dep,
            "description": desc,
            "installed": ok,
            "version": info if ok else None,
            "status": "ok" if ok else "warning",
        })

    critical_status = _severity(critical)
    return {
        "python_version": py_version,
        "critical_deps": critical,
        "optional_deps": optional,
        "status": critical_status,
        "message": "Python 环境就绪" if critical_status == "ok" else "关键依赖缺失，后端无法正常运行",
    }

# ------------------------------------------------------------------ #
#  2. HELIOS++ 可执行文件检测（外部引擎，仅存在性检查）
# ------------------------------------------------------------------ #

def diagnose_helios_executable() -> dict:
    """检测 HELIOS++ 可执行文件是否存在（外部仿真引擎，仅做存在性检查）。

    HELIOS++ 不由 FeHALS 提供，因此只检测可执行文件能否找到，
    不做版本探测、不检测资源目录完整性等细项。
    """
    import shutil
    import os

    path = cfg.HELIOS_PATH

    # 解析路径
    if os.sep in path or "/" in path:
        resolved = str(Path(path)) if Path(path).exists() else None
    else:
        resolved = shutil.which(path)

    found = resolved is not None
    executable = False
    if found:
        if os.name == "nt":
            executable = True
        else:
            executable = bool(os.access(resolved, os.X_OK))

    if not found:
        return {
            "path": path,
            "resolved_path": None,
            "found": False,
            "executable": False,
            "status": "warning",
            "message": f"未找到 HELIOS++ 可执行文件「{path}」，仿真功能将不可用。（HELIOS++ 为外部依赖，需自行安装）",
        }

    if not executable:
        return {
            "path": path,
            "resolved_path": resolved,
            "found": True,
            "executable": False,
            "status": "warning",
            "message": f"HELIOS++ 已找到「{resolved}」但无执行权限（chmod +x）。",
        }

    return {
        "path": path,
        "resolved_path": resolved,
        "found": True,
        "executable": True,
        "status": "ok",
        "message": "HELIOS++ 可执行文件就绪",
    }

# ------------------------------------------------------------------ #
#  3. 静态工作目录检测
# ------------------------------------------------------------------ #

def diagnose_static_dirs() -> list:
    """检测后端静态工作目录是否就绪。"""
    dirs = [
        ("models", "模型目录", cfg.MODELS_DIR),
        ("trajectories", "航迹目录", cfg.TRAJECTORIES_DIR),
        ("configs", "配置目录", cfg.CONFIGS_DIR),
        ("results", "结果目录", cfg.RESULTS_DIR),
    ]
    results = []
    for key, label, path in dirs:
        exists = Path(path).exists()
        results.append({
            "name": key,
            "label": label,
            "path": str(path),
            "exists": exists,
            "status": "ok" if exists else "error",
            "message": "就绪" if exists else "目录不存在",
        })
    return results

# ------------------------------------------------------------------ #
#  4. 汇总诊断
# ------------------------------------------------------------------ #

async def diagnose_all() -> dict[str, Any]:
    """执行全量环境诊断，返回结构化报告。

    整体状态（overall）基于 FeHALS 产品最小可用性判断：
      - Python 后端环境 + 静态工作目录 = ok / warning / error
      - HELIOS++ 为外部依赖，不影响整体状态（仅作为附加信息展示）
    """
    python_env = diagnose_python_env()
    static_dirs = diagnose_static_dirs()
    helios = diagnose_helios_executable()

    # 整体状态 = Python 环境 + 静态目录（HELIOS++ 不参与整体判断）
    overall_items = [python_env] + static_dirs
    overall = _severity(overall_items)

    summary = {
        "ok": "FeHALS 运行环境就绪",
        "warning": "FeHALS 运行环境存在非关键问题",
        "error": "FeHALS 运行环境检测失败，服务不可用",
    }

    return {
        "overall": overall,
        "summary": summary.get(overall, ""),
        "python_env": python_env,
        "static_dirs": static_dirs,
        "helios_executable": helios,
    }