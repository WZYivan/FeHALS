"""WebSocket 日志推送：WS /ws/logs/{task_id}

连接后先回放已有日志，若任务仍在运行则持续推送增量消息，
直至收到 complete/error 或客户端断开。
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services import helios_service

router = APIRouter()


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
