# FeHALS 仿真任务队列管理设计

> 对应 TODO：`仿真任务队列管理（多任务顺序执行、并发调度、状态显示）`
>
> 适用范围：`backend/`（FastAPI + asyncio）与 `frontend/`（Vue 3 + Pinia）

---

## 1. 现状分析（为什么要做队列）

当前实现（`backend/app/services/helios_service.py`）：

- `POST /api/simulation/run` 校验并生成 XML 后，调用 `run_simulation()`；
- `run_simulation()` 立即 `asyncio.create_task(_run(task))` —— **fire-and-forget**，任何任务都会被立即执行；
- 任务存放在进程内 `TASKS: dict`，无队列、无并发限制、无持久化，后端重启即丢失；
- 前端 `stores/simulation.js` 只保存**单个**任务状态；`App.vue` 里 `if (simStore.status === 'running')` 直接拦截，
  因此 UI 上表现为"一次只能跑一个"，但后端实际并没有任何约束。

**问题**：

| 问题 | 表现 |
| --- | --- |
| 无顺序保证 | 同时提交 10 个任务会同时启动 10 个 helios++ 子进程，内存/CPU 打满 |
| 无并发上限 | 大模型 + 多任务时可能 OOM 或机器卡死 |
| 无统一状态视图 | 前端只看得见"当前任务"，历史任务状态只能靠重新轮询单个 task_id |
| 无排队语义 | 任务要么立即运行，要么被前端挡住；没有"排队中"这一状态 |
| 无统一日志入口 | 每个任务一个 WS，前端无法同时观察多任务进度 |

---

## 2. 设计目标与范围

**目标**

1. **顺序执行**：任务按提交顺序排队（FIFO），可配置并发度；并发度为 1 时严格顺序执行。
2. **并发调度**：可配置最大并发数 `N`，最多 `N` 个 helios++ 子进程同时运行，其余任务排队等待。
3. **状态显示**：前端以任务列表展示全部任务（排队/运行/完成/失败/取消），支持进度、日志切换、取消与重排。
4. **向后兼容**：保留现有单任务 API 与 `/ws/logs/{task_id}` 行为，已有前端可继续工作。

**非目标（v1 不做）**

- 队列持久化到数据库/磁盘（v2 可选，见 §9）；
- 任务优先级抢占（仅预留字段）；
- 分布式/多进程队列（单进程 asyncio 足够，HELIOS++ 由子进程承载）。

---

## 3. 总体架构

```
┌─────────────────────────── 前端 (Vue 3 + Pinia) ───────────────────────────┐
│  TaskQueuePanel (新)         LogConsole (改)          App.vue (改)          │
│  任务列表 / 状态徽章 / 进度  按选中任务显示日志         提交任务不再阻塞       │
└───────────────┬──────────────────────┬───────────────────────▲─────────────┘
                │ REST /api/simulation/*│ WS /ws/queue + /ws/logs/{id}
┌───────────────▼──────────────────────▼───────────────────────┴─────────────┐
│                        FastAPI 后端（单进程 asyncio）                       │
│  api/routes.py ──► services/task_queue.py (新增) ──► helios_service.py     │
│  提交/队列/取消      SimulationQueueManager 单例        SimulationTask 复用  │
│  ┌──────────────────────────────────────────────────────────────┐          │
│  │  _pending: deque/PriorityQueue    _slots: Semaphore(N)       │          │
│  │  _dispatcher(): 循环 → 出队 → acquire 槽位 → _run(task)      │          │
│  └──────────────────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │ subprocess
                                    ▼
                              helios++ 引擎
```

调度器为**单一后台协程**：从待执行队列取任务，通过 `asyncio.Semaphore(max_concurrency)` 控制同时运行的 helios++ 数量。

---

## 4. 核心数据模型

### 4.1 任务状态机

```
                 submit
                    │
                    ▼
              ┌──────────┐    dispatcher 取到    ┌─────────┐   rc==0   ┌───────────┐
              │  queued  │ ────────────────────► │ running │ ────────► │ completed │
              └──────────┘                       └─────────┘           └───────────┘
                    │                                │  │                  ▲
                    │ cancel                         │  │ rc!=0 / 异常      │
                    ▼                                │  └──────────────────┤
              ┌──────────┐                           ▼                     │
              │ cancelled│                     ┌─────────┐                │
              └──────────┘                     │  failed  │ ◄──────────────┘
                                               └─────────┘
```

- `queued`（排队中）：已通过校验并生成 XML，等待槽位；
- `running`（运行中）：子进程执行中；
- `completed` / `failed` / `cancelled`：终态。

> 状态字段追加到现有 `SimulationTask`，原 `pending` 语义拆分为 `queued`（入队未跑）与 `running`。

### 4.2 `SimulationTask` 扩展（`helios_service.py`）

```python
@dataclass
class SimulationTask:
    task_id: str
    survey_path: str
    output_dir: str
    output_format: str
    # 新增字段
    status: str = "queued"          # queued | running | completed | failed | cancelled
    priority: int = 0               # 预留：数字越小越先（v1 全部为 0）
    submitted_at: float             # time.time()，FIFO 排序键
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    # 保留字段
    progress: int = 0
    message: str = ""
    cancelled: bool = False
    result_file: str | None = None
    logs: list = field(default_factory=list)
    process: asyncio.subprocess.Process | None = None
    subscribers: list = field(default_factory=list)
```

### 4.3 Pydantic schema（`models/schemas.py` 新增）

```python
class QueueTaskBrief(BaseModel):
    task_id: str
    status: str
    progress: int
    message: str
    priority: int
    submitted_at: float
    output_format: str

class QueueSnapshot(BaseModel):
    max_concurrency: int
    running_count: int
    queued_count: int
    tasks: List[QueueTaskBrief]   # 按（排队序 + 运行序）排列
```

---

## 5. 队列管理器（后端核心，新增 `services/task_queue.py`）

### 5.1 单例结构与调度循环

```python
class SimulationQueueManager:
    def __init__(self, max_concurrency: int = 1):
        self.max_concurrency = max_concurrency
        self._slots = asyncio.Semaphore(max_concurrency)
        self._pending: deque[SimulationTask] = deque()   # FIFO 待执行队列
        self._tasks: dict[str, SimulationTask] = {}      # 全部任务注册表
        self._order: list[str] = []                      # 显示顺序（提交序）
        self._dispatcher_task: asyncio.Task | None = None
        self._subscribers: set[asyncio.Queue] = set()    # 队列级 WS 订阅者
        self._start_dispatcher()

    def submit(self, task: SimulationTask) -> None:
        """入队：注册任务，追加到待执行队列，广播 queued 事件。"""
        self._tasks[task.task_id] = task
        self._order.append(task.task_id)
        self._pending.append(task)
        self._broadcast("task_queued", task)

    async def _dispatcher(self) -> None:
        """唯一调度协程：串行地从队列取任务并派发（子进程并行由 Semaphore 控制）。"""
        while True:
            if not self._pending:
                await asyncio.sleep(0.1)
                continue
            task = self._pending.popleft()
            if task.status == "cancelled":        # 排队中已被取消，跳过
                continue
            await self._slots.acquire()           # 无空闲槽位则在此等待
            asyncio.create_task(self._run_and_release(task))
            task.status = "running"
            task.started_at = time.time()
            self._broadcast("task_started", task)
```

> **关键点**：`_dispatcher` 是唯一的"取任务"入口，天然保证 FIFO；子进程并行度由
> `_slots`（`Semaphore(N)`）控制。`N = 1` 即严格顺序执行，`N > 1` 即并发调度。

### 5.2 运行与释放槽位

```python
    async def _run_and_release(self, task: SimulationTask) -> None:
        try:
            await helios_service.run_task(task)   # 原 _run(task) 的逻辑移入
        finally:
            self._slots.release()
            self._broadcast("task_finished", task)   # completed / failed / cancelled
```

`helios_service._run(task, assets)` 现有逻辑基本不动，仅两处调整：

1. 状态从 `pending → running` 改为**由调度器设置**，`_run` 只负责 `running → completed/failed`；
2. 完成/失败时把 `finished_at` 填好并返回终态，由管理器广播。

### 5.3 取消语义

```python
    async def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task is None:
            return False
        if task.status == "queued":
            task.status = "cancelled"          # 出队时跳过
            self._broadcast("task_cancelled", task)
            return True
        if task.status == "running":
            return await helios_service.cancel(task_id)   # kill 子进程（现有逻辑）
        return False                            # 终态不可取消
```

### 5.4 状态快照与队列重排

```python
    def snapshot(self) -> QueueSnapshot:
        running = [t for t in self._tasks.values() if t.status == "running"]
        queued = [t for t in self._pending if t.status == "queued"]
        tasks = queued + running + [已结束任务按 finished_at 倒序]
        return QueueSnapshot(...)

    def reorder(self, task_id: str, before_task_id: str | None) -> bool:
        """v2 可选：在待执行队列内移动任务（仅 queued 状态可移动）。"""
```

---

## 6. REST API 设计（`api/routes.py` 修改）

| 方法 | 路径 | 说明 | 变化 |
| --- | --- | --- | --- |
| POST | `/api/simulation/run` | 提交任务（入队） | **改**：不再直接 `create_task`，改为 `queue.submit(task)`；立即返回 `task_id + status=queued` |
| GET | `/api/simulation/queue` | 队列快照 | **新增** |
| GET | `/api/simulation/status/{task_id}` | 单任务状态 | 不变（`status` 增加 `queued`） |
| GET | `/api/simulation/logs/{task_id}` | 单任务日志 | 不变 |
| POST | `/api/simulation/cancel/{task_id}` | 取消任务 | **改**：改为 `queue.cancel()`（支持取消排队中的任务） |
| POST | `/api/simulation/queue/{task_id}/reorder` | 重排 | **新增（可选）** |
| POST | `/api/simulation/queue/pause` / `resume` | 暂停/恢复派发 | **新增（可选 v2）** |

`run` 端点改造示意：

```python
@router.post("/simulation/run")
async def run_simulation(req: SimulationRunRequest):
    # ...原有校验 + 生成 scene/survey XML（保持不变）...
    task = SimulationTask(...)          # 只构造，不启动
    task_manager.submit(task)           # 入队，由调度器决定何时运行
    return {"task_id": task.task_id, "status": task.status}
```

---

## 7. WebSocket 设计（`api/websocket.py` 修改）

### 7.1 队列级广播 `/ws/queue`（新增）

```json
{"type": "task_queued",     "task": {"task_id": "...", "status": "queued", ...}}
{"type": "task_started",    "task": {"task_id": "...", "status": "running", ...}}
{"type": "task_progress",   "task_id": "...", "percent": 42}
{"type": "task_finished",   "task_id": "...", "status": "completed"}
{"type": "task_cancelled",  "task_id": "..."}
```

- 连接时先发送完整快照（`{"type":"snapshot", ...}`），之后增量推送；
- 一个 WS 即可驱动整个任务列表面板，避免前端为每个任务各开一条连接。

### 7.2 任务级日志 `/ws/logs/{task_id}`（保留）

- 保持现有回放 + 增量推送语义；
- 前端"选中某个任务"时才连接该任务的日志流。

---

## 8. 前端设计（Vue 3 + Pinia）

### 8.1 `stores/simulation.js` 重构

```js
state: () => ({
  tasks: {},                // taskId -> {taskId, status, progress, message, logs: [], result}
  order: [],                // 提交顺序
  selectedTaskId: null,     // 当前日志/结果视图选中的任务
  maxConcurrency: 1,
  status: 'idle',           // 兼容旧字段：当前主任务状态
  ...params 不变
})
```

- `addLog(taskId, level, message)`：日志按任务隔离；
- `handleQueueEvent(msg)`：根据 `type` 更新 `tasks` / `order`；
- 保留旧字段做 getter 兼容，`App.vue` 逐步迁移。

### 8.2 新增 `components/TaskQueuePanel.vue`

- 列表行：状态徽章（排队/运行/完成/失败/取消）、进度条、提交时间、输出格式；
- 操作：选中查看日志/结果、取消（queued/running 可用）、重排（可选）；
- 顶部显示：`运行中 x / 排队中 y / 最大并发 N`；
- 空状态：无任务时提示"暂无仿真任务"。

### 8.3 修改 `App.vue` / `LogConsole.vue`

- **移除** `if (simStore.status === 'running') return` 拦截 —— 允许多任务排队提交；
- 工具栏"执行仿真"按钮始终可用（提交即入队），状态徽章显示当前选中任务；
- `LogConsole` 顶部增加任务切换下拉，`connectLogWS(selectedTaskId)` 动态重连；
- 队列面板常驻或作为新 Tab（建议新增"任务队列"Tab）。

### 8.4 `useHeliosAPI.js` 增补

```js
const getQueue = () => api.get('/simulation/queue').then(r => r.data)
const cancelTask = (id) => api.post(`/simulation/cancel/${id}`).then(r => r.data)
export function connectQueueWS(handlers) { /* WS /ws/queue */ }
```

---

## 9. 配置与并发度

`backend/app/config.py` 新增：

```python
# 最大并发仿真数（1 = 严格顺序执行；>1 = 并发调度）
MAX_CONCURRENT_SIMULATIONS = int(os.getenv("FEHALS_MAX_CONCURRENT", "1"))
```

前端 `SettingsPanel.vue` 增加展示/设置项（只读展示后端值，v1）。

---

## 10. 关键设计决策与权衡

| 决策 | 选择 | 理由 |
| --- | --- | --- |
| 队列实现 | `asyncio.deque` + 单个 dispatcher 协程 | 简单、单进程够用、FIFO 语义清晰 |
| 并发控制 | `asyncio.Semaphore(N)` | 子进程是 CPU/IO 混合，Semaphore 足够，无需线程池 |
| 默认并发度 | 1（顺序执行） | HELIOS++ 单任务已吃满多核，默认顺序最安全；用户可调 |
| 队列持久化 | v1 不持久化 | 后端重启丢队列但结果文件仍在；v2 用 JSON 快照恢复 |
| 任务日志 | 每任务内存 list + WS | 与现有一致；大规模时 v2 落盘 |
| 状态显示 | 队列级 WS 快照 + 增量 | 一个连接管所有任务，简单可靠 |
| 兼容性 | 保留单任务 API/WS | 不破坏现有前端与调试脚本 |

---

## 11. 实施步骤（建议顺序）

1. **后端状态与队列核心**
   - `helios_service.py`：`SimulationTask` 增加 `queued/submitted_at/priority` 字段，`_run` 状态拆分；
   - 新增 `services/task_queue.py`：`SimulationQueueManager`（submit/dispatcher/semaphore/cancel/snapshot/broadcast）；
   - `config.py`：`MAX_CONCURRENT_SIMULATIONS`。
2. **后端 API/WS**
   - `routes.py`：`run` 改为入队；新增 `/simulation/queue`；`cancel` 走队列；
   - `websocket.py`：新增 `/ws/queue` 广播。
3. **前端**
   - 重构 `stores/simulation.js` 为多任务；新增 `TaskQueuePanel.vue`；改 `App.vue`、`LogConsole.vue`、`useHeliosAPI.js`。
4. **测试**
   - 单元测试：顺序执行（并发=1 时同时只 1 个 running）、并发=2 时最多 2 个、取消 queued 直接终态、取消 running kill 子进程；
   - API 测试：提交→queued→running→completed 全链路。
5. **（可选 v2）** 优先级、重排、暂停/恢复、队列 JSON 持久化。

---

## 12. 验收标准

- [ ] 并发度为 1 时，连续提交 5 个任务严格按 FIFO 顺序执行（第 2 个在第 1 个完成后才启动）；
- [ ] 并发度为 2 时，最多 2 个 helios++ 同时运行，第 3 个排队；
- [ ] 前端任务列表实时显示每个任务的 queued/running/completed/failed/cancelled 与进度；
- [ ] 排队中的任务可取消；运行中的任务可取消（复用现有 kill）；
- [ ] 旧接口 `/simulation/status/{id}`、`/ws/logs/{id}` 行为不变。
