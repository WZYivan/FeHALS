"""FeHALS 后端启动脚本。

用法（在 conda 环境 FeHALS 中）：
    conda activate FeHALS
    python run.py

默认在 http://localhost:8000 启动 FastAPI 服务。
"""
import uvicorn

from app.config import HOST, PORT


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
