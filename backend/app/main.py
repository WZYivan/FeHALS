"""FastAPI 应用入口：装配 CORS、静态文件与路由。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.api.websocket import router as ws_router
from app.config import CORS_ORIGINS, STATIC_DIR, ensure_dirs

app = FastAPI(title="FeHALS Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
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
