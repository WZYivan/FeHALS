"""任务队列管理器单元测试。

通过 monkeypatch helios_service.run_task 模拟子进程执行，
验证顺序执行、并发调度与排队中取消三个核心行为。
"""
import asyncio
import time
import unittest

from app.services import helios_service
from app.services.task_queue import SimulationQueueManager


def make_task(task_id: str) -> helios_service.SimulationTask:
    return helios_service.SimulationTask(task_id, "survey.xml", "/tmp/out", "XYZ")


class _FakeRunner:
    """记录并发峰值与执行顺序的假 run_task。"""

    def __init__(self, delay: float = 0.03):
        self.delay = delay
        self.running = 0
        self.max_running = 0
        self.started: list = []
        self.finished: list = []

    async def __call__(self, task, assets=None):
        self.running += 1
        self.max_running = max(self.max_running, self.running)
        self.started.append(task.task_id)
        await asyncio.sleep(self.delay)
        task.status = "completed"
        task.finished_at = time.time()
        self.finished.append(task.task_id)
        self.running -= 1


class QueueSequentialTest(unittest.IsolatedAsyncioTestCase):
    async def test_fifo_sequential_execution(self):
        """并发度为 1 时严格顺序执行。"""
        fake = _FakeRunner()
        original = helios_service.run_task
        helios_service.run_task = fake
        try:
            manager = SimulationQueueManager(max_concurrency=1)
            t1 = make_task("sim_t1")
            t2 = make_task("sim_t2")
            manager.submit(t1)
            manager.submit(t2)
            await asyncio.sleep(0.2)

            self.assertEqual(fake.max_running, 1)
            self.assertEqual(fake.started, ["sim_t1", "sim_t2"])
            self.assertEqual(t1.status, "completed")
            self.assertEqual(t2.status, "completed")
            # 顺序执行：t1 完成后 t2 才开始
            self.assertLess(
                fake.finished.index("sim_t1"), fake.started.index("sim_t2")
            )
        finally:
            helios_service.run_task = original


class QueueConcurrencyTest(unittest.IsolatedAsyncioTestCase):
    async def test_max_concurrency_limit(self):
        """并发度为 2 时最多 2 个任务同时运行。"""
        fake = _FakeRunner(delay=0.05)
        original = helios_service.run_task
        helios_service.run_task = fake
        try:
            manager = SimulationQueueManager(max_concurrency=2)
            for i in range(4):
                manager.submit(make_task(f"sim_c{i}"))
            await asyncio.sleep(0.3)

            self.assertLessEqual(fake.max_running, 2)
            self.assertEqual(fake.max_running, 2)  # 确实发生过并发
            self.assertEqual(len(fake.finished), 4)
        finally:
            helios_service.run_task = original


class QueueCancelTest(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_queued_task(self):
        """排队中的任务可取消且不会执行。"""
        fake = _FakeRunner(delay=0.05)
        original = helios_service.run_task
        helios_service.run_task = fake
        try:
            manager = SimulationQueueManager(max_concurrency=1)
            t1 = make_task("sim_k1")
            t2 = make_task("sim_k2")
            manager.submit(t1)
            manager.submit(t2)
            ok = await manager.cancel("sim_k2")
            await asyncio.sleep(0.2)

            self.assertTrue(ok)
            self.assertEqual(t2.status, "cancelled")
            self.assertNotIn("sim_k2", fake.started)
            self.assertEqual(t1.status, "completed")
        finally:
            helios_service.run_task = original


if __name__ == "__main__":
    unittest.main()
