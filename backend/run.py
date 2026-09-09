"""FeHALS 后端启动脚本。

用法（在 conda 环境 FeHALS 中）：
    conda activate FeHALS
    python run.py

默认在 http://localhost:8000 启动 FastAPI 服务。
"""
import os

import uvicorn

from app.config import HOST, PORT

# reload 模式可通过环境变量 FEHALS_RELOAD 关闭（Windows 上建议关闭，
# 因为 uvicorn reloader 子进程可能与 asyncio 子进程创建冲突）。
# 默认开启，保持 Linux 开发环境行为不变。
_RELOAD = os.getenv("FEHALS_RELOAD", "true").lower() not in ("0", "false", "no")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=_RELOAD)
