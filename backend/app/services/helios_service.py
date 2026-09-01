"""HELIOS++ 仿真执行服务。

通过 asyncio 子进程调用 helios++ 可执行文件，实时捕获 stdout/stderr，
写入任务日志并通过 WebSocket 推送给前端。
"""
import asyncio
import re
import time
import uuid
from pathlib import Path
from typing import Optional

from app.config import HELIOS_ASSETS, HELIOS_PATH, RESULTS_DIR, SIMULATION_TIMEOUT

# 任务注册表：task_id -> SimulationTask
TASKS: dict = {}


class SimulationTask:
    """单个仿真任务的运行态。"""

    def __init__(self, task_id: str, survey_path: str, output_dir: str, output_format: str):
        self.task_id = task_id
        self.survey_path = survey_path
        self.output_dir = output_dir
        self.output_format = output_format
        self.status = "pending"
        self.progress = 0
        self.message = ""
        self.cancelled = False
        self.result_file: Optional[str] = None
        self.logs: list = []
        self.process: Optional[asyncio.subprocess.Process] = None
        self.subscribers: list = []  # asyncio.Queue 列表

    async def push(self, msg: dict) -> None:
        """追加一条消息并广播给所有订阅者。"""
        msg.setdefault("timestamp", time.strftime("%Y-%m-%d %H:%M:%S"))
        self.logs.append(msg)
        for q in list(self.subscribers):
            await q.put(msg)


def _new_task_id() -> str:
    return f"sim_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"


def run_simulation(
    survey_path: str,
    output_dir: str,
    output_format: str = "LAS",
    assets: Optional[list] = None,
) -> SimulationTask:
    """启动一次仿真，立即返回任务对象（后台异步执行）。"""
    task = SimulationTask(_new_task_id(), survey_path, output_dir, output_format)
    TASKS[task.task_id] = task
    asyncio.create_task(_run(task, assets or HELIOS_ASSETS))
    return task


def get_task(task_id: str) -> Optional[SimulationTask]:
    return TASKS.get(task_id)


def subscribe(task_id: str) -> Optional[asyncio.Queue]:
    """为任务注册一个日志订阅队列。"""
    task = TASKS.get(task_id)
    if task is None:
        return None
    q: asyncio.Queue = asyncio.Queue()
    task.subscribers.append(q)
    return q


def unsubscribe(task_id: str, q: asyncio.Queue) -> None:
    task = TASKS.get(task_id)
    if task and q in task.subscribers:
        task.subscribers.remove(q)


async def cancel(task_id: str) -> bool:
    """终止正在运行的仿真任务。"""
    task = TASKS.get(task_id)
    if task is None or task.process is None:
        return False
    task.cancelled = True
    task.process.kill()
    return True


async def _run(task: SimulationTask, assets: list) -> None:
    cmd = [HELIOS_PATH, task.survey_path]
    for a in assets:
        cmd += ["--assets", a]
    cmd += ["--output", task.output_dir]
    if task.output_format in ("LAS", "LAZ"):
        cmd.append("--lasOutput")
    if task.output_format == "LAZ":
        cmd.append("--zipOutput")

    await task.push({"type": "log", "level": "INFO", "message": f"执行命令: {' '.join(cmd)}"})

    try:
        task.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError:
        task.status = "failed"
        task.message = f"未找到 HELIOS++ 可执行文件（{HELIOS_PATH}），请检查 HELIOS_PATH 配置。"
        await task.push({"type": "error", "message": task.message})
        return
    except OSError as e:
        task.status = "failed"
        task.message = f"启动 HELIOS++ 失败：{e}"
        await task.push({"type": "error", "message": task.message})
        return

    task.status = "running"
    await task.push({"type": "log", "level": "INFO", "message": "仿真开始..."})

    async def _read_stream() -> None:
        assert task.process is not None and task.process.stdout is not None
        while True:
            line = await task.process.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").rstrip()
            if not text:
                continue
            level = "INFO"
            low = text.lower()
            if any(k in low for k in ("error", "fatal", "exception", "failed")):
                level = "ERROR"
            elif any(k in low for k in ("warn", "warning")):
                level = "WARNING"
            await task.push({"type": "log", "level": level, "message": text})
            # 尽力解析进度百分比（如 "Survey 50.00%"）
            m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
            if m:
                pct = int(float(m.group(1)))
                if 0 <= pct <= 100:
                    task.progress = pct
                    await task.push({"type": "progress", "percent": pct, "message": text})

    try:
        await asyncio.wait_for(_read_stream(), timeout=SIMULATION_TIMEOUT)
        await task.process.wait()
    except asyncio.TimeoutError:
        if task.process is not None:
            task.process.kill()
            await task.process.wait()
        task.status = "failed"
        task.message = f"仿真超时（>{SIMULATION_TIMEOUT}s），已终止。"
        await task.push({"type": "error", "message": task.message})
        return

    rc = task.process.returncode
    if rc == 0:
        task.status = "completed"
        task.progress = 100
        task.result_file = _find_output(task.output_dir)
        task.message = "仿真完成"
        await task.push(
            {"type": "complete", "result_file": task.result_file, "message": "仿真完成"}
        )
    else:
        task.status = "failed"
        if task.cancelled:
            task.message = "已取消"
        else:
            task.message = f"HELIOS++ 退出码 {rc}"
            # 该 HELIOS++ 构建未启用 LAS 输出时，--lasOutput 会触发空指针崩溃
            if task.output_format in ("LAS", "LAZ") and _log_contains(task, "LASwriter"):
                task.message = "当前 HELIOS++ 构建未启用 LAS 输出支持，请改用 XYZ 输出格式"
        await task.push({"type": "error", "message": task.message})


def _find_output(output_dir: str) -> Optional[str]:
    """在输出目录中递归查找最新生成的点云文件。

    HELIOS++ 的输出嵌套在 output_dir/<survey>/<timestamp>/ 下，
    且同时会生成航迹（*_trajectory.txt），需排除航迹文件。
    """
    d = Path(output_dir)
    if not d.exists():
        return None
    files = [
        f for f in d.rglob("*")
        if f.is_file()
        and f.suffix.lower() in (".las", ".laz", ".xyz")
        and "trajectory" not in f.stem.lower()
    ]
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return str(files[0])


def _log_contains(task: SimulationTask, needle: str) -> bool:
    """判断任务日志中是否包含指定关键字。"""
    return any(needle in str(m.get("message", "")) for m in task.logs)
