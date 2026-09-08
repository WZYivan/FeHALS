"""仿真任务队列管理器。

单例 SimulationQueueManager 统一负责：
- 任务入队（FIFO）
- 顺序执行 / 并发调度（asyncio.Semaphore 控制最大并发数）
- 队列级状态广播（供 /ws/queue 使用）

「单个任务怎么跑」由 helios_service.run_task 负责，
「何时跑」由本模块的 _dispatcher 决定。
"""
import asyncio
import time
from collections import deque
from typing import Optional

from app.config import MAX_CONCURRENT_SIMULATIONS
from app.services import helios_service

# 已结束状态集合
_TERMINAL_STATES = {"completed", "failed", "cancelled"}


class SimulationQueueManager:
    """仿真任务队列管理器（单进程单例）。"""

    def __init__(self, max_concurrency: int = MAX_CONCURRENT_SIMULATIONS):
        self.max_concurrency = max(1, int(max_concurrency))
        # 槽位信号量：控制同时运行的 helios++ 子进程数
        self._slots = asyncio.Semaphore(self.max_concurrency)
        # 待执行队列（FIFO）
        self._pending: deque = deque()
        # 提交顺序（task_id 列表）
        self._order: list = []
        # 队列级 WS 订阅者
        self._subscribers: set = set()
        # 后台调度协程
        self._dispatcher_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # 超时检测
    # ------------------------------------------------------------------

    async def _check_stale_tasks(self) -> None:
        """定期检查卡住的任务（运行超过 5 分钟且进度为 0）。"""
        while True:
            await asyncio.sleep(30)  # 每 30 秒检查一次
            now = time.time()
            for task in list(helios_service.TASKS.values()):
                if task.status == "running" and task.started_at:
                    elapsed = now - task.started_at
                    # 运行超过 5 分钟且进度为 0，可能是卡住了
                    if elapsed > 300 and task.progress == 0:
                        task.status = "failed"
                        task.finished_at = now
                        task.message = "任务超时（运行超过5分钟无进度），已自动终止"
                        await task.push({"type": "error", "message": task.message})
                        self._broadcast({
                            "type": "task_finished",
                            "task_id": task.task_id,
                            "status": task.status,
                            "task": self._brief(task),
                        })

    def start(self) -> None:
        """启动后台调度协程和超时检查（幂等）。"""
        if self._dispatcher_task is None or self._dispatcher_task.done():
            self._dispatcher_task = asyncio.create_task(self._dispatcher())
            asyncio.create_task(self._check_stale_tasks())

    # ------------------------------------------------------------------
    # 入队 / 取消
    # ------------------------------------------------------------------

    def submit(self, task: helios_service.SimulationTask) -> None:
        """任务入队：注册到全局注册表并追加到待执行队列末尾。

        先同步写日志并广播 task_queued，再启动调度协程，
        保证订阅者总是先收到 queued 再收到 started（避免乱序回跳）。
        """
        helios_service.register(task)
        self._order.append(task.task_id)
        self._pending.append(task)
        task.push_nowait(
            {
                "type": "log",
                "level": "INFO",
                "message": f"任务已入队（队列位置 {len(self._pending)}）",
            }
        )
        self._broadcast(
            {"type": "task_queued", "task_id": task.task_id, "task": self._brief(task)}
        )
        self.start()

    async def cancel(self, task_id: str) -> bool:
        """取消任务：排队中直接标记取消，运行中 kill 子进程。"""
        task = helios_service.get_task(task_id)
        if task is None:
            return False

        if task.status == "queued":
            # 从待执行队列中移除任务
            try:
                self._pending.remove(task)
            except ValueError:
                pass  # 任务可能已被调度器取出但尚未开始运行

            task.status = "cancelled"
            task.finished_at = time.time()
            task.message = "已取消"
            await task.push({"type": "error", "message": "已取消"})
            self._broadcast(
                {"type": "task_cancelled", "task_id": task_id, "task": self._brief(task)}
            )
            return True

        if task.status == "running":
            ok = await helios_service.cancel_running(task_id)
            if ok:
                task.status = "cancelled"
                task.finished_at = time.time()
                task.message = "任务已取消"
                await task.push({"type": "error", "message": "任务已取消"})
                self._broadcast(
                    {"type": "task_cancelled", "task_id": task_id, "task": self._brief(task)}
                )
            return ok

        # 终态不可取消
        return False

    # ------------------------------------------------------------------
    # 调度核心
    # ------------------------------------------------------------------

    async def _dispatcher(self) -> None:
        """唯一取任务协程：按 FIFO 出队，获得槽位后派发执行。

        子进程并行度由 self._slots 控制：
        - max_concurrency = 1 时严格顺序执行；
        - max_concurrency > 1 时最多 N 个任务同时运行。
        """
        while True:
            if not self._pending:
                await asyncio.sleep(0.1)
                continue

            task = self._pending.popleft()
            # 排队期间被取消的任务直接跳过
            if task.status == "cancelled":
                continue

            # 无空闲槽位则阻塞等待（此时不阻塞出队判断）
            await self._slots.acquire()
            task.status = "running"
            task.started_at = time.time()
            self._broadcast(
                {"type": "task_started", "task_id": task.task_id, "task": self._brief(task)}
            )
            asyncio.create_task(self._run_and_release(task))

    async def _run_and_release(self, task: helios_service.SimulationTask) -> None:
        """运行任务并在结束后释放槽位、广播终态。"""
        # 订阅任务级日志流，转发为队列级事件
        q = helios_service.subscribe(task.task_id)
        if q is not None:
            asyncio.create_task(self._forward_task_events(task.task_id, q))

        try:
            await helios_service.run_task(task)
        finally:
            if q is not None:
                helios_service.unsubscribe(task.task_id, q)
            self._slots.release()
            self._broadcast(
                {
                    "type": "task_finished",
                    "task_id": task.task_id,
                    "status": task.status,
                    "task": self._brief(task),
                }
            )

    async def _forward_task_events(self, task_id: str, q: asyncio.Queue) -> None:
        """把任务级消息（log/progress/complete/error）转发为队列级广播。"""
        while True:
            msg = await q.get()
            out = dict(msg)
            out["task_id"] = task_id
            self._broadcast(out)
            if out.get("type") in ("complete", "error"):
                break

    # ------------------------------------------------------------------
    # 快照 / 广播
    # ------------------------------------------------------------------

    def snapshot(self) -> dict:
        """返回队列快照：运行中 + 排队中 + 最近结束的任务。"""
        running = [t for t in helios_service.TASKS.values() if t.status == "running"]
        queued = [t for t in self._pending if t.status == "queued"]
        finished = [
            t for t in helios_service.TASKS.values() if t.status in _TERMINAL_STATES
        ]
        finished.sort(key=lambda t: t.finished_at or 0, reverse=True)

        tasks = [self._brief(t) for t in queued + running + finished]
        return {
            "max_concurrency": self.max_concurrency,
            "running_count": len(running),
            "queued_count": len(queued),
            "tasks": tasks,
        }

    def subscribe(self) -> asyncio.Queue:
        """注册一个队列级广播订阅队列。"""
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def _broadcast(self, msg: dict) -> None:
        """向所有队列级订阅者同步推送消息（失败订阅者自动清理）。"""
        for q in list(self._subscribers):
            try:
                q.put_nowait(msg)
            except Exception:
                self._subscribers.discard(q)

    @staticmethod
    def _brief(task: helios_service.SimulationTask) -> dict:
        """任务摘要（用于快照与队列广播）。"""
        return {
            "task_id": task.task_id,
            "status": task.status,
            "progress": task.progress,
            "message": task.message,
            "priority": task.priority,
            "output_format": task.output_format,
            "submitted_at": task.submitted_at,
            "started_at": task.started_at,
            "finished_at": task.finished_at,
            "result_file": task.result_file,
        }


# 全局单例
queue_manager = SimulationQueueManager()
