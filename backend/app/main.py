"""FastAPI 应用入口：装配 CORS、静态文件与路由。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.api.websocket import router as ws_router
from app.config import CORS_ORIGINS, STATIC_DIR, ensure_dirs

app = FastAPI(title="FeHALS Backend", version="0.1.0")

# CORS：允许前端（默认 http://localhost:5173）以及直连后端 8000 端口的场景。
# 注意 allow_credentials 与 "*" 不能共存：当来源含通配符时关闭 credentials，
# 由 FEHALS_CORS_ORIGINS 环境变量可改为显式来源列表（此时可开启 credentials）。
_allow_origins = CORS_ORIGINS or ["*"]
_allow_credentials = "*" not in _allow_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.on_event("startup")
async def _startup() -> None:
    ensure_dirs()


# 静态文件（模型 / 航迹 / 配置 / 结果）
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(api_router)
app.include_router(ws_router)


@app.get("/")
async def root():
    return {"service": "FeHALS Backend", "docs": "/docs"}
