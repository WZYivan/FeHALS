"""WebSocket 路由 - 日志推送与实时仿真数据推送"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import asyncio

from app.services import helios_service

router = APIRouter()

# 存储活跃的 WebSocket 连接
active_connections = {}
# 存储每个任务的实时仿真运行器
active_runners = {}


@router.websocket("/ws/logs/{task_id}")
async def ws_logs(websocket: WebSocket, task_id: str):
    await websocket.accept()

    task = helios_service.get_task(task_id)
    if task is None:
        await websocket.send_json({"type": "error", "message": f"任务不存在：{task_id}"})
        await websocket.close()
        return

    # 回放已有日志
    for msg in task.logs:
        await websocket.send_json(msg)

    # 已结束则直接关闭
    if task.status in ("completed", "failed"):
        await websocket.close()
        return

    q = helios_service.subscribe(task_id)
    if q is None:
        await websocket.close()
        return

    try:
        while True:
            msg = await q.get()
            await websocket.send_json(msg)
            if msg.get("type") in ("complete", "error"):
                break
    except WebSocketDisconnect:
        pass
    finally:
        helios_service.unsubscribe(task_id, q)


@router.websocket("/ws/live/{task_id}")
async def websocket_live(websocket: WebSocket, task_id: str):
    """WebSocket 端点：用于实时推送仿真数据"""
    await websocket.accept()
    active_connections[task_id] = websocket

    try:
        while True:
            # 接收客户端的控制消息（如暂停、播放、停止）
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") == "pause":
                    await handle_pause(task_id)
                elif msg.get("action") == "resume":
                    await handle_resume(task_id)
                elif msg.get("action") == "stop":
                    await handle_stop(task_id)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        active_connections.pop(task_id, None)


async def push_live_data(task_id: str, data_type: str, data: dict):
    """推送实时数据到前端"""
    ws = active_connections.get(task_id)
    if ws:
        try:
            await ws.send_text(json.dumps({
                "type": data_type,
                "data": data,
                "task_id": task_id
            }))
        except Exception:
            pass


def create_live_callbacks(task_id: str):
    """创建回调函数，用于实时推送数据"""
    def on_point(point):
        asyncio.create_task(push_live_data(task_id, "point", point))

    def on_trajectory(traj):
        asyncio.create_task(push_live_data(task_id, "trajectory", traj))

    def on_log(level, msg):
        asyncio.create_task(push_live_data(task_id, "log", {"level": level, "message": msg}))

    return on_point, on_trajectory, on_log


async def handle_pause(task_id):
    # 暂停动画逻辑（前端控制）
    pass

async def handle_resume(task_id):
    pass

async def handle_stop(task_id):
    runner = active_runners.get(task_id)
    if runner:
        runner.cancel()