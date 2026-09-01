"""REST API 路由。

模型 / 航迹 / 配置 / 仿真 / 结果 / 缓存 六类资源。
"""
import shutil
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import CONFIGS_DIR, MODELS_DIR, RESULTS_DIR, TRAJECTORIES_DIR
from app.models.schemas import ConfigRequest, SimulationRunRequest, TrajectoryRequest
from app.services import (
    config_generator,
    helios_service,
    pointcloud_parser,
    trajectory_generator,
)

router = APIRouter(prefix="/api")

# 模型注册表：model_id -> {filename, path, url, ext}（单进程内有效）
MODEL_REGISTRY: dict = {}

# 允许上传的模型格式（其中仅 .obj 可参与 HELIOS++ 仿真）
ALLOWED_MODEL_EXTS = {".obj", ".gltf", ".glb", ".stl"}

_CHUNK = 1024 * 1024


# ---------------------------- 模型管理 ----------------------------

@router.post("/models/upload")
async def upload_model(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_MODEL_EXTS:
        raise HTTPException(
            400, f"不支持的模型格式：{ext or '未知'}（支持 {', '.join(sorted(ALLOWED_MODEL_EXTS))}）"
        )
    model_id = f"mod_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    dest = MODELS_DIR / f"{model_id}{ext}"
    # 分块流式写入，避免大文件占用内存
    with open(dest, "wb") as f:
        while chunk := await file.read(_CHUNK):
            f.write(chunk)

    url = f"/static/models/{dest.name}"
    # 推断 OBJ 模型的 up 轴（Y-up 需在 HELIOS++ 与前端一致地旋转到 Z-up）
    up = config_generator.detect_up_axis(str(dest)) if ext == ".obj" else "z"
    MODEL_REGISTRY[model_id] = {
        "filename": file.filename or dest.name,
        "path": str(dest),
        "url": url,
        "ext": ext,
        "up": up,
    }
    return {"model_id": model_id, "filename": file.filename, "url": url, "up": up}


@router.get("/models")
async def list_models():
    models = [
        {"id": mid, "name": m["filename"], "url": m["url"], "up": m.get("up", "z")}
        for mid, m in MODEL_REGISTRY.items()
    ]
    return {"models": models}


@router.delete("/models/{model_id}")
async def delete_model(model_id: str):
    m = MODEL_REGISTRY.pop(model_id, None)
    if m:
        Path(m["path"]).unlink(missing_ok=True)
    return {"success": True}


# ---------------------------- 航迹管理 ----------------------------

@router.post("/trajectory/generate")
async def generate_trajectory(req: TrajectoryRequest):
    if not req.waypoints:
        raise HTTPException(400, "航点列表不能为空")
    result = trajectory_generator.generate(req.waypoints, req.altitude)
    return {
        "file_id": result["file_id"],
        "download_url": f"/api/trajectories/download/{result['file_id']}",
        "point_count": result["point_count"],
    }


@router.get("/trajectories")
async def list_trajectories():
    items = []
    for p in sorted(TRAJECTORIES_DIR.glob("*.trj")):
        items.append(
            {"id": p.stem, "created": p.stat().st_mtime, "point_count": None}
        )
    return {"trajectories": items}


@router.get("/trajectories/download/{file_id}")
async def download_trajectory(file_id: str):
    p = TRAJECTORIES_DIR / f"{file_id}.trj"
    if not p.exists():
        raise HTTPException(404, "航迹文件不存在")
    return FileResponse(str(p), filename=f"{file_id}.trj", media_type="text/plain")


# ---------------------------- 配置管理 ----------------------------

@router.post("/config/generate")
async def generate_config(req: ConfigRequest):
    config_id = config_generator.store_config(req.model_dump())
    return {
        "config_id": config_id,
        "config_path": f"/static/configs/{config_id}.json",
    }


# ---------------------------- 仿真执行 ----------------------------

@router.post("/simulation/run")
async def run_simulation(req: SimulationRunRequest):
    # 1. 校验航迹
    traj_path = TRAJECTORIES_DIR / f"{req.trajectory_id}.trj"
    if not traj_path.exists():
        raise HTTPException(404, f"航迹不存在：{req.trajectory_id}")

    # 2. 校验配置
    try:
        params = config_generator.get_config(req.config_id)
    except KeyError:
        raise HTTPException(404, f"配置不存在：{req.config_id}")

    # 3. 校验模型（可选）
    model_path = None
    model_up = "z"
    if req.scene_model_id:
        m = MODEL_REGISTRY.get(req.scene_model_id)
        if not m:
            raise HTTPException(404, f"模型不存在：{req.scene_model_id}")
        if m["ext"] != ".obj":
            raise HTTPException(400, "仅 OBJ 格式模型可参与 HELIOS++ 仿真（GLTF/STL 仅用于三维展示）")
        model_path = m["path"]
        model_up = m.get("up", "z")

    # 4. 生成 scene + survey XML
    scene_xml, scene_id = config_generator.generate_scene_xml(model_path, up=model_up)
    survey_xml = config_generator.generate_survey_xml(
        scene_xml_path=str(scene_xml),
        scene_id=scene_id,
        traj_path=str(traj_path),
        params=params,
    )

    # 5. 启动仿真
    output_dir = RESULTS_DIR / f"sim_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_format = params.get("output_format", "LAS")

    task = helios_service.run_simulation(str(survey_xml), str(output_dir), output_format)
    return {"task_id": task.task_id}


@router.get("/simulation/status/{task_id}")
async def simulation_status(task_id: str):
    task = helios_service.get_task(task_id)
    if task is None:
        raise HTTPException(404, f"任务不存在：{task_id}")
    return {
        "task_id": task.task_id,
        "status": task.status,
        "progress": task.progress,
        "message": task.message,
        "result_file": task.result_file,
    }


@router.get("/simulation/logs/{task_id}")
async def simulation_logs(task_id: str):
    task = helios_service.get_task(task_id)
    if task is None:
        raise HTTPException(404, f"任务不存在：{task_id}")
    return {"logs": task.logs}


@router.post("/simulation/cancel/{task_id}")
async def cancel_simulation(task_id: str):
    ok = await helios_service.cancel(task_id)
    return {"success": ok}


# ---------------------------- 结果管理 ----------------------------

@router.get("/results/{task_id}")
async def get_result(task_id: str):
    task = helios_service.get_task(task_id)
    if task is None:
        raise HTTPException(404, f"任务不存在：{task_id}")
    if task.status != "completed" or not task.result_file:
        raise HTTPException(409, f"任务尚未完成或未产生结果（当前状态：{task.status}）")

    parsed = pointcloud_parser.parse(task.result_file)
    return {
        "file_path": parsed["file_path"],
        "point_count": parsed["point_count"],
        "bounds": parsed["bounds"],
        "points": parsed["points"],
        "intensity": parsed["intensity"],
    }


@router.get("/results/{task_id}/download")
async def download_result(task_id: str, format: str = "las"):
    task = helios_service.get_task(task_id)
    if task is None:
        raise HTTPException(404, f"任务不存在：{task_id}")
    if not task.result_file:
        raise HTTPException(409, f"任务尚未产生结果（当前状态：{task.status}）")
    p = Path(task.result_file)
    return FileResponse(str(p), filename=p.name, media_type="application/octet-stream")


# ---------------------------- 缓存管理 ----------------------------

CACHE_DIRS = {
    "models": MODELS_DIR,
    "trajectories": TRAJECTORIES_DIR,
    "configs": CONFIGS_DIR,
    "results": RESULTS_DIR,
}

# 缓存目录名 → 中文标签
CACHE_LABELS = {
    "models": "模型",
    "trajectories": "航迹",
    "configs": "配置",
    "results": "结果",
}


@router.get("/cache")
async def cache_stats():
    """返回各缓存目录的文件数及总大小（字节）。"""
    stats = {}
    for key, d in CACHE_DIRS.items():
        if not d.exists():
            stats[key] = {"label": CACHE_LABELS.get(key, key), "count": 0, "size": 0}
            continue
        count = 0
        size = 0
        for f in d.iterdir():
            if f.is_file() and f.name != ".gitkeep":
                count += 1
                size += f.stat().st_size
        stats[key] = {"label": CACHE_LABELS.get(key, key), "count": count, "size": size}
    return {"cache": stats}


@router.delete("/cache/{cache_type}")
async def clear_cache(cache_type: str):
    """清空指定缓存目录（保留 .gitkeep）。"""
    d = CACHE_DIRS.get(cache_type)
    if d is None:
        raise HTTPException(404, f"未知缓存类型：{cache_type}（可选：{', '.join(CACHE_DIRS.keys())}）")
    if not d.exists():
        return {"success": True, "type": cache_type, "removed": 0}
    removed = 0
    for f in d.iterdir():
        if f.is_file() and f.name != ".gitkeep":
            f.unlink()
            removed += 1
    return {"success": True, "type": cache_type, "removed": removed}
