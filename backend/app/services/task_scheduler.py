"""多任务调度器：在原有单任务仿真引擎之上叠加队列与并发调度层。

设计原则：
  - 总开关 enabled=False 时，调度器完全不介入，原有 /simulation/run 单任务流程不受任何影响。
  - enabled=True 时，提供三种模式：
      single     : 单任务阻塞——有任务在运行或排队时拒绝新任务（保留原单任务阻塞逻辑）
      sequential : 顺序执行——所有任务入队，FIFO 逐个执行
      concurrent : 并发调度——最多 max_concurrent 个任务同时运行，超出部分排队
  - 调度器仅管理"何时启动"，实际执行仍委托给 helios_service，
    任务创建后即注册到 helios_service.TASKS，原有 status/logs/cancel/results 接口可直接复用。
"""
import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from app.config import CONFIGS_DIR, HELIOS_ASSETS
from app.services import helios_service

# 调度器配置持久化文件（与仿真配置同目录，随缓存管理可清理）
_SCHEDULER_CONFIG_FILE = CONFIGS_DIR / "scheduler.json"

# 合法调度模式
_VALID_MODES = {"single", "sequential", "concurrent"}


@dataclass
class SchedulerConfig:
    """调度器配置。"""

    enabled: bool = False  # 总开关：False 时调度器完全不介入
    mode: str = "sequential"  # single | sequential | concurrent
    max_concurrent: int = 2  # concurrent 模式下的最大并发数


@dataclass
class ScheduledTask:
    """调度器管理的任务条目，包装底层 SimulationTask 并附加调度元数据。"""

    task_id: str
    name: str
    status: str = "queued"  # queued | running | completed | failed | cancelled
    progress: int = 0
    message: str = ""
    result_file: Optional[str] = None
    queued_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    # 启动参数（由 create_task 预创建后持有，待 start_task 时使用）
    _assets: Optional[list] = None
    _monitor: Optional[asyncio.Task] = None  # 完成监听协程

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "result_file": self.result_file,
            "queued_at": self.queued_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class TaskScheduler:
    """多任务调度器（单例）。"""

    _instance: Optional["TaskScheduler"] = None

    def __init__(self) -> None:
        self.config = SchedulerConfig()
        self._queue: asyncio.Queue[ScheduledTask] = asyncio.Queue()
        self._tasks: dict[str, ScheduledTask] = {}
        self._running: set[str] = set()
        self._worker_task: Optional[asyncio.Task] = None
        self._load_config()

    # ------------------------------------------------------------------
    # 单例
    # ------------------------------------------------------------------
    @classmethod
    def instance(cls) -> "TaskScheduler":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # 配置持久化
    # ------------------------------------------------------------------
    def _load_config(self) -> None:
        if _SCHEDULER_CONFIG_FILE.exists():
            try:
                data = json.loads(_SCHEDULER_CONFIG_FILE.read_text(encoding="utf-8"))
                self.config.enabled = bool(data.get("enabled", False))
                mode = data.get("mode", "sequential")
                self.config.mode = mode if mode in _VALID_MODES else "sequential"
                self.config.max_concurrent = max(1, int(data.get("max_concurrent", 2)))
            except (OSError, ValueError):
                pass

    def _save_config(self) -> None:
        CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
        _SCHEDULER_CONFIG_FILE.write_text(
            json.dumps(asdict(self.config), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_config(self) -> dict:
        return {
            **asdict(self.config),
            "queue_size": self._queue.qsize(),
            "running_count": len(self._running),
            "total_count": len(self._tasks),
        }

    def set_config(
        self,
        enabled: Optional[bool] = None,
        mode: Optional[str] = None,
        max_concurrent: Optional[int] = None,
    ) -> dict:
        if enabled is not None:
            self.config.enabled = bool(enabled)
        if mode is not None:
            if mode not in _VALID_MODES:
                raise ValueError(f"非法调度模式：{mode}（可选：{', '.join(sorted(_VALID_MODES))}）")
            self.config.mode = mode
        if max_concurrent is not None:
            self.config.max_concurrent = max(1, int(max_concurrent))
        self._save_config()
        if self.config.enabled:
            self._ensure_worker()
        return self.get_config()

    # ------------------------------------------------------------------
    # 任务提交
    # ------------------------------------------------------------------
    async def submit(
        self,
        survey_path: str,
        output_dir: str,
        output_format: str = "LAS",
        assets: Optional[list] = None,
        name: Optional[str] = None,
    ) -> ScheduledTask:
        """提交一个仿真任务到调度器。

        根据当前模式决定立即启动还是入队等待。任务预创建后即注册到 helios_service.TASKS。
        """
        task_id = f"sim_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
        display_name = name or f"任务-{task_id[-6:]}"

        # 预创建底层仿真任务（注册到 helios_service.TASKS，但不启动）
        helios_service.create_task(survey_path, output_dir, output_format, task_id=task_id)

        st = ScheduledTask(
            task_id=task_id,
            name=display_name,
            _assets=assets or list(HELIOS_ASSETS),
        )
        self._tasks[task_id] = st

        if self.config.mode == "single":
            # 单任务阻塞模式：有运行中或排队任务则拒绝
            if self._running or self._queue.qsize() > 0:
                # 清理已预创建的任务
                helios_service.TASKS.pop(task_id, None)
                self._tasks.pop(task_id, None)
                raise RuntimeError("单任务模式下已有任务正在运行，请等待其完成后再提交新任务")
            st.status = "running"
            st.started_at = time.time()
            self._running.add(task_id)
            helios_service.start_task(task_id, st._assets)
            self._monitor_task(st)
        elif self.config.mode == "sequential":
            await self._queue.put(st)
            self._ensure_worker()
        elif self.config.mode == "concurrent":
            if len(self._running) < self.config.max_concurrent:
                st.status = "running"
                st.started_at = time.time()
                self._running.add(task_id)
                helios_service.start_task(task_id, st._assets)
                self._monitor_task(st)
            else:
                await self._queue.put(st)
                self._ensure_worker()

        return st

    # ------------------------------------------------------------------
    # 任务查询与管理
    # ------------------------------------------------------------------
    def list_tasks(self) -> list[dict]:
        """返回所有任务（按入队时间倒序）。"""
        tasks = sorted(self._tasks.values(), key=lambda t: t.queued_at, reverse=True)
        return [t.to_dict() for t in tasks]

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        return self._tasks.get(task_id)

    def remove_task(self, task_id: str) -> bool:
        """从调度器列表中移除一个已结束（completed/failed/cancelled）的任务。

        运行中或排队中的任务不可移除（需先取消）。同时从 helios_service.TASKS 中注销。
        """
        st = self._tasks.get(task_id)
        if st is None:
            return False
        if st.status in ("queued", "running"):
            return False
        self._tasks.pop(task_id, None)
        helios_service.TASKS.pop(task_id, None)
        return True

    def clear_completed(self) -> int:
        """清除所有已结束（completed/failed/cancelled）的任务，返回清除数量。"""
        to_remove = [
            tid for tid, st in self._tasks.items()
            if st.status in ("completed", "failed", "cancelled")
        ]
        for tid in to_remove:
            self._tasks.pop(tid, None)
            helios_service.TASKS.pop(tid, None)
        return len(to_remove)

    async def cancel_task(self, task_id: str) -> bool:
        """取消一个排队中或运行中的任务。"""
        st = self._tasks.get(task_id)
        if st is None:
            return False
        if st.status == "queued":
            # 从队列中移除（asyncio.Queue 没有直接 remove，标记后跳过）
            st.status = "cancelled"
            st.message = "已取消"
            st.finished_at = time.time()
            helios_service.TASKS.pop(task_id, None)
            return True
        if st.status == "running":
            return await helios_service.cancel(task_id)
        return False

    # ------------------------------------------------------------------
    # 内部：Worker 与完成监听
    # ------------------------------------------------------------------
    def _ensure_worker(self) -> None:
        """确保 worker 协程在运行。"""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())

    async def _worker(self) -> None:
        """后台 worker：持续检查空闲槽位，从队列中取任务启动。"""
        while True:
            if not self.config.enabled:
                await asyncio.sleep(1.0)
                continue

            # 计算当前模式允许的最大并发数
            if self.config.mode in ("single", "sequential"):
                max_run = 1
            else:
                max_run = self.config.max_concurrent

            # 填充空闲槽位
            while len(self._running) < max_run and self._queue.qsize() > 0:
                try:
                    st = self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if st.status == "cancelled":
                    # 已被取消的排队任务，跳过
                    continue
                st.status = "running"
                st.started_at = time.time()
                self._running.add(st.task_id)
                helios_service.start_task(st.task_id, st._assets)
                self._monitor_task(st)

            await asyncio.sleep(0.3)

    def _monitor_task(self, st: ScheduledTask) -> None:
        """启动一个协程监听底层仿真任务，完成后更新调度状态并触发 worker。

        采用「消息订阅（实时）+ 轮询兜底（每2秒）」双机制：
        - 消息订阅保证进度和完成事件的实时推送
        - 轮询兜底防止消息丢失，并检测进程启动超时（如未安装 HELIOS++ 导致子进程卡住）
        """
        async def _monitor() -> None:
            q = helios_service.subscribe(st.task_id)
            if q is None:
                return
            try:
                while True:
                    # 等待消息，2秒超时则轮询一次 helios 任务状态作为兜底
                    try:
                        msg = await asyncio.wait_for(q.get(), timeout=2.0)
                    except asyncio.TimeoutError:
                        sim_task = helios_service.get_task(st.task_id)
                        if sim_task is not None:
                            # 同步进度（消息可能丢失）
                            if sim_task.progress > st.progress:
                                st.progress = sim_task.progress
                            # helios 任务已结束但消息未送达
                            if sim_task.status == "completed":
                                st.status = "completed"
                                st.progress = 100
                                st.message = sim_task.message or "仿真完成"
                                st.result_file = sim_task.result_file
                                st.finished_at = time.time()
                                break
                            if sim_task.status == "failed":
                                st.status = "failed"
                                st.message = sim_task.message or "仿真失败"
                                st.finished_at = time.time()
                                break
                            # 进程启动超时：helios 任务长期停留在 pending
                            if sim_task.status == "pending" and st.started_at:
                                if time.time() - st.started_at > 30:
                                    st.status = "failed"
                                    st.message = "仿真进程启动超时（可能未安装 HELIOS++ 或可执行文件路径配置错误）"
                                    st.finished_at = time.time()
                                    break
                        continue

                    # 处理实时消息
                    if msg.get("type") == "complete":
                        st.status = "completed"
                        st.progress = 100
                        st.message = msg.get("message", "仿真完成")
                        st.result_file = msg.get("result_file")
                        st.finished_at = time.time()
                        break
                    if msg.get("type") == "error":
                        st.status = "failed"
                        st.message = msg.get("message", "仿真失败")
                        st.finished_at = time.time()
                        break
                    if msg.get("type") == "progress":
                        st.progress = int(msg.get("percent", st.progress))
            finally:
                helios_service.unsubscribe(st.task_id, q)
                self._running.discard(st.task_id)
                self._ensure_worker()

        st._monitor = asyncio.create_task(_monitor())


# 模块级单例访问入口
def get_scheduler() -> TaskScheduler:
    return TaskScheduler.instance()
