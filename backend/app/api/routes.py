"""REST API 路由。

模型 / 航迹 / 配置 / 仿真 / 结果 / 缓存 六类资源。
多任务调度器：/api/scheduler + /api/tasks（新增，不影响原有单任务流程）。
"""
import json
import numpy as np
import shutil
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import CONFIGS_DIR, MODELS_DIR, RESULTS_DIR, TRAJECTORIES_DIR
from app.models.schemas import (
    BatchTaskSubmitRequest,
    ConfigRequest,
    CoverageRequest,
    SchedulerConfigUpdate,
    SimulationRunRequest,
    TaskSubmitRequest,
    TrajectoryRequest,
)
from app.services import (
    config_generator,
    env_service,
    helios_service,
    pointcloud_parser,
    trajectory_generator,
)
from app.services.task_scheduler import get_scheduler
from ..services.coverage import CoverageAnalyzer
router = APIRouter(prefix="/api")

# 模型注册表：model_id -> {filename, path, url, ext}（单进程内有效）
MODEL_REGISTRY: dict = {}

# 允许上传的模型格式（其中仅 .obj 可参与 HELIOS++ 仿真）
ALLOWED_MODEL_EXTS = {".obj", ".gltf", ".glb", ".stl"}

_CHUNK = 1024 * 1024


# ---------------------------- 模型管理 ----------------------------

def _restore_model_registry() -> None:
    """启动时从模型目录恢复注册表。

    注册表存于内存，后端重启即丢失；模型文件本身持久化在 MODELS_DIR。
    上传时落盘 {model_id}.json 清单（记录原始文件名），此处连同无清单的
    孤儿模型文件一并恢复注册，避免后端重启后已上传模型"消失"。
    """
    for p in sorted(MODELS_DIR.iterdir()):
        ext = p.suffix.lower()
        if ext not in ALLOWED_MODEL_EXTS:
            continue
        model_id = p.stem
        if model_id in MODEL_REGISTRY:
            continue
        manifest = MODELS_DIR / f"{model_id}.json"
        filename = p.name
        if manifest.exists():
            try:
                filename = json.loads(manifest.read_text(encoding="utf-8")).get("filename", p.name)
            except (OSError, ValueError):
                pass
        MODEL_REGISTRY[model_id] = {
            "filename": filename,
            "path": str(p),
            "url": f"/static/models/{p.name}",
            "ext": ext,
            "up": config_generator.detect_up_axis(str(p)) if ext == ".obj" else "z",
        }


_restore_model_registry()


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
    # 落盘清单（原始文件名），供后端重启后恢复注册表
    (MODELS_DIR / f"{model_id}.json").write_text(
        json.dumps({"filename": file.filename or dest.name}, ensure_ascii=False),
        encoding="utf-8",
    )
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
        (MODELS_DIR / f"{model_id}.json").unlink(missing_ok=True)
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
    model_entries: list[tuple[str, str]] = []
    if req.scene_model_ids:
        for mid in req.scene_model_ids:
            m = MODEL_REGISTRY.get(mid)
            if not m:
                raise HTTPException(404, f"模型不存在：{mid}")
            if m["ext"] != ".obj":
                raise HTTPException(400, f"模型「{m['filename']}」不是 OBJ 格式（仅 OBJ 可参与 HELIOS++ 仿真）")
            model_entries.append((m["path"], m.get("up", "z")))

    # 4. 生成 scene + survey XML
    scene_xml, scene_id = config_generator.generate_scene_xml(model_entries if model_entries else None)
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
        "stats": parsed["stats"],
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

# ---------------------------- 环境诊断 ----------------------------

@router.get("/env/diagnose")
async def diagnose_env():
    """检测 HELIOS++ 运行环境：可执行文件、资源目录完整性、静态工作目录。"""
    return await env_service.diagnose_all()

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
# ==================== 点云覆盖度分析 ====================

@router.post("/coverage/analyze")
async def analyze_coverage(request: CoverageRequest):
    """分析点云覆盖度：投影到 XY 平面网格，返回密度矩阵与统计指标。"""
    try:
        points = np.array(request.points)
        analyzer = CoverageAnalyzer(grid_size=request.grid_size)
        return analyzer.analyze(points)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 多任务调度器（新增，不影响原有单任务流程） ====================

def _prepare_simulation(req: TaskSubmitRequest) -> dict:
    """仿真任务提交前的准备工作：校验航迹/配置/模型，生成 scene+survey XML 和输出目录。

    与 /simulation/run 的准备逻辑一致，但不启动仿真，返回启动所需参数供调度器使用。
    """
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
    model_entries: list[tuple[str, str]] = []
    if req.scene_model_ids:
        for mid in req.scene_model_ids:
            m = MODEL_REGISTRY.get(mid)
            if not m:
                raise HTTPException(404, f"模型不存在：{mid}")
            if m["ext"] != ".obj":
                raise HTTPException(400, f"模型「{m['filename']}」不是 OBJ 格式（仅 OBJ 可参与 HELIOS++ 仿真）")
            model_entries.append((m["path"], m.get("up", "z")))

    # 4. 生成 scene + survey XML
    scene_xml, scene_id = config_generator.generate_scene_xml(model_entries if model_entries else None)
    survey_xml = config_generator.generate_survey_xml(
        scene_xml_path=str(scene_xml),
        scene_id=scene_id,
        traj_path=str(traj_path),
        params=params,
    )

    # 5. 创建输出目录（不启动仿真）
    output_dir = RESULTS_DIR / f"sim_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_format = params.get("output_format", "LAS")

    return {
        "survey_path": str(survey_xml),
        "output_dir": str(output_dir),
        "output_format": output_format,
    }


@router.get("/scheduler")
async def get_scheduler_config():
    """获取调度器配置及运行统计。"""
    return get_scheduler().get_config()


@router.put("/scheduler")
async def update_scheduler_config(req: SchedulerConfigUpdate):
    """更新调度器配置（enabled / mode / max_concurrent）。

    enabled=False 时调度器完全不介入，原有单任务流程不受影响。
    """
    try:
        return get_scheduler().set_config(
            enabled=req.enabled,
            mode=req.mode,
            max_concurrent=req.max_concurrent,
            paused=req.paused,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/tasks")
async def list_scheduler_tasks():
    """列出调度器管理的所有任务（含排队中、运行中、已完成、失败）。"""
    return {"tasks": get_scheduler().list_tasks()}


@router.post("/tasks")
async def submit_task(req: TaskSubmitRequest):
    """提交单个仿真任务到调度器。

    若调度器未启用（enabled=False），返回 409 提示先启用调度器或使用 /simulation/run。
    """
    scheduler = get_scheduler()
    if not scheduler.config.enabled:
        raise HTTPException(409, "多任务调度器未启用。请先启用调度器，或使用 /api/simulation/run 执行单任务。")

    prepared = _prepare_simulation(req)
    try:
        st = await scheduler.submit(
            survey_path=prepared["survey_path"],
            output_dir=prepared["output_dir"],
            output_format=prepared["output_format"],
            name=req.name,
        )
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return st.to_dict()


@router.post("/tasks/batch")
async def submit_batch_tasks(req: BatchTaskSubmitRequest):
    """批量提交仿真任务到调度器。逐个准备并提交，返回每个任务的结果。"""
    scheduler = get_scheduler()
    if not scheduler.config.enabled:
        raise HTTPException(409, "多任务调度器未启用。请先启用调度器，或使用 /api/simulation/run 执行单任务。")

    results = []
    for i, task_req in enumerate(req.tasks):
        try:
            prepared = _prepare_simulation(task_req)
            st = await scheduler.submit(
                survey_path=prepared["survey_path"],
                output_dir=prepared["output_dir"],
                output_format=prepared["output_format"],
                name=task_req.name or f"批量任务-{i + 1}",
            )
            results.append({"success": True, "task": st.to_dict()})
        except (HTTPException, RuntimeError) as e:
            detail = e.detail if isinstance(e, HTTPException) else str(e)
            results.append({"success": False, "error": detail, "name": task_req.name or f"批量任务-{i + 1}"})
    return {"results": results}


@router.delete("/tasks/{task_id}")
async def remove_scheduler_task(task_id: str):
    """从调度器列表中移除一个已结束（completed/failed/cancelled）的任务。"""
    ok = get_scheduler().remove_task(task_id)
    if not ok:
        raise HTTPException(409, "任务不存在或尚未结束（排队中/运行中的任务需先取消）")
    return {"success": True}


@router.post("/tasks/clear")
async def clear_completed_tasks():
    """清除所有已结束（completed/failed/cancelled）的任务。"""
    removed = get_scheduler().clear_completed()
    return {"success": True, "removed": removed}


@router.post("/tasks/{task_id}/cancel")
async def cancel_scheduler_task(task_id: str):
    """取消一个排队中或运行中的调度器任务。"""
    ok = await get_scheduler().cancel_task(task_id)
    if not ok:
        raise HTTPException(404, f"任务不存在或无法取消：{task_id}")
    return {"success": True}
