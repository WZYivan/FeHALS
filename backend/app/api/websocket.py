"""WebSocket 端点。

- WS /ws/logs/{task_id}：单任务日志流（回放 + 增量推送）
- WS /ws/queue        ：任务队列状态流（快照 + 队列事件广播）
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services import helios_service, task_queue

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
    if task.status in ("completed", "failed", "cancelled"):
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


@router.websocket("/ws/queue")
async def ws_queue(websocket: WebSocket):
    """任务队列状态流：连接时发送完整快照，之后推送队列事件。"""
    await websocket.accept()

    await websocket.send_json(
        {"type": "snapshot", **task_queue.queue_manager.snapshot()}
    )

    q = task_queue.queue_manager.subscribe()
    try:
        while True:
            msg = await q.get()
            await websocket.send_json(msg)
    except WebSocketDisconnect:
        pass
    finally:
        task_queue.queue_manager.unsubscribe(q)
