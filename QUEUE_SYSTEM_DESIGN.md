# 仿真任务队列管理系统设计文档

## 1. 系统概述

### 1.1 需求分析

基于现有的 HELIOS++ 仿真执行机制，需要实现一个任务队列管理系统，支持：

- **多任务顺序执行**：任务按提交顺序排队执行
- **并发调度**：支持配置最大并发数（如 2-4 个任务同时运行）
- **状态显示**：实时显示队列状态、任务进度
- **优先级管理**：支持任务优先级调整
- **资源控制**：防止系统过载
- **任务管理**：暂停、恢复、取消、重试

### 1.2 现有机制分析

**优点：**
- ✅ 异步任务执行（asyncio）
- ✅ 实时日志推送（WebSocket）
- ✅ 任务状态管理
- ✅ 进度解析

**不足：**
- ❌ 无队列机制，所有任务立即启动
- ❌ 无并发控制，可能导致资源耗尽
- ❌ 无任务优先级
- ❌ 无任务依赖管理
- ❌ 任务持久化不足（重启后丢失）

---

## 2. 系统架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 UI                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 任务提交面板 │  │ 队列监控面板 │  │ 任务详情面板 │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────────┬────────────────────────────────────┘
                         │ REST API / WebSocket
┌────────────────────────┴────────────────────────────────────┐
│                      后端 API 层                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  /api/queue/*  -  队列管理 API 端点                   │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────┐
│                   任务队列管理器                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 任务队列     │  │ 调度器       │  │ 执行器池     │      │
│  │ (优先级队列) │  │ (并发控制)   │  │ (Worker Pool)│      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 任务存储     │  │ 状态管理     │  │ 事件广播     │      │
│  │ (持久化)     │  │ (状态机)     │  │ (WebSocket)  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────┐
│                  HELIOS++ 仿真服务                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  helios_service.py  -  现有仿真执行逻辑              │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

#### 2.2.1 任务队列（TaskQueue）
- 优先级队列实现
- 支持 FIFO / 优先级排序
- 线程安全

#### 2.2.2 调度器（Scheduler）
- 并发控制（信号量）
- 任务分配逻辑
- 资源监控

#### 2.2.3 执行器池（WorkerPool）
- Worker 管理
- 任务执行
- 异常处理

#### 2.2.4 任务存储（TaskStorage）
- SQLite 持久化
- 任务状态持久化
- 历史记录查询

#### 2.2.5 状态管理（StateManager）
- 任务状态机
- 状态转换验证
- 事件触发

#### 2.2.6 事件广播（EventBroadcaster）
- WebSocket 推送
- 多客户端支持
- 消息队列

---

## 3. 数据模型设计

### 3.1 任务状态枚举

```python
class TaskStatus(str, Enum):
    PENDING = "pending"          # 等待中
    QUEUED = "queued"            # 已入队
    RUNNING = "running"          # 运行中
    PAUSED = "paused"            # 已暂停
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"            # 失败
    CANCELLED = "cancelled"      # 已取消
    RETRYING = "retrying"        # 重试中
```

### 3.2 任务优先级

```python
class TaskPriority(int, Enum):
    LOW = 1
    NORMAL = 5
    HIGH = 10
    URGENT = 20
```

### 3.3 任务模型

```python
class QueuedTask(BaseModel):
    task_id: str                      # 任务ID
    name: str                         # 任务名称
    status: TaskStatus                # 当前状态
    priority: TaskPriority            # 优先级
    
    # 仿真参数
    survey_path: str                  # Survey XML 路径
    output_dir: str                   # 输出目录
    output_format: str                # 输出格式
    
    # 时间信息
    created_at: datetime              # 创建时间
    queued_at: Optional[datetime]     # 入队时间
    started_at: Optional[datetime]    # 开始时间
    completed_at: Optional[datetime]  # 完成时间
    
    # 执行信息
    progress: int = 0                 # 进度 (0-100)
    message: str = ""                 # 状态消息
    result_file: Optional[str]        # 结果文件
    error_message: Optional[str]      # 错误信息
    
    # 重试信息
    retry_count: int = 0              # 重试次数
    max_retries: int = 3              # 最大重试次数
    
    # 依赖关系
    depends_on: List[str] = []        # 依赖的任务ID列表
    
    # 元数据
    metadata: Dict[str, Any] = {}     # 自定义元数据
```

### 3.4 队列配置

```python
class QueueConfig(BaseModel):
    max_concurrent_tasks: int = 2     # 最大并发任务数
    max_queue_size: int = 100         # 最大队列大小
    default_priority: TaskPriority = TaskPriority.NORMAL
    enable_auto_retry: bool = True    # 自动重试
    retry_delay: int = 60             # 重试延迟（秒）
    task_timeout: int = 3600          # 任务超时（秒）
```

---

## 4. API 设计

### 4.1 队列管理 API

#### 4.1.1 提交任务到队列
```http
POST /api/queue/submit
Content-Type: application/json

{
  "name": "UAV 扫描任务 #1",
  "priority": "normal",
  "survey_path": "/path/to/survey.xml",
  "output_dir": "/path/to/output",
  "output_format": "XYZ",
  "metadata": {
    "user": "admin",
    "project": "project_A"
  }
}

Response:
{
  "task_id": "queue_1234567890_abc123",
  "status": "queued",
  "queue_position": 3,
  "estimated_wait_time": 120
}
```

#### 4.1.2 获取队列状态
```http
GET /api/queue/status

Response:
{
  "total_tasks": 10,
  "queued": 5,
  "running": 2,
  "completed": 3,
  "failed": 0,
  "max_concurrent": 2,
  "queue": [
    {
      "task_id": "queue_xxx",
      "name": "任务名称",
      "status": "queued",
      "priority": 5,
      "queue_position": 1
    }
  ]
}
```

#### 4.1.3 获取任务列表
```http
GET /api/queue/tasks?status=running&limit=20&offset=0

Response:
{
  "tasks": [...],
  "total": 50,
  "limit": 20,
  "offset": 0
}
```

#### 4.1.4 获取任务详情
```http
GET /api/queue/tasks/{task_id}

Response:
{
  "task_id": "queue_xxx",
  "name": "任务名称",
  "status": "running",
  "progress": 45,
  "created_at": "2026-09-04T10:00:00Z",
  "started_at": "2026-09-04T10:05:00Z",
  ...
}
```

#### 4.1.5 更新任务优先级
```http
PATCH /api/queue/tasks/{task_id}/priority
Content-Type: application/json

{
  "priority": "high"
}
```

#### 4.1.6 暂停任务
```http
POST /api/queue/tasks/{task_id}/pause
```

#### 4.1.7 恢复任务
```http
POST /api/queue/tasks/{task_id}/resume
```

#### 4.1.8 取消任务
```http
POST /api/queue/tasks/{task_id}/cancel
```

#### 4.1.9 重试任务
```http
POST /api/queue/tasks/{task_id}/retry
```

#### 4.1.10 删除任务
```http
DELETE /api/queue/tasks/{task_id}
```

#### 4.1.11 批量操作
```http
POST /api/queue/batch
Content-Type: application/json

{
  "action": "cancel",  // cancel | pause | resume | delete
  "task_ids": ["task1", "task2", "task3"]
}
```

#### 4.1.12 清空队列
```http
POST /api/queue/clear?status=pending
```

#### 4.1.13 更新队列配置
```http
PUT /api/queue/config
Content-Type: application/json

{
  "max_concurrent_tasks": 4,
  "enable_auto_retry": true
}
```

#### 4.1.14 获取队列统计
```http
GET /api/queue/statistics

Response:
{
  "total_submitted": 100,
  "total_completed": 85,
  "total_failed": 5,
  "success_rate": 0.95,
  "average_execution_time": 180,
  "average_wait_time": 60
}
```

### 4.2 WebSocket 事件

#### 连接
```
ws://localhost:8000/ws/queue
```

#### 事件类型

**队列状态更新**
```json
{
  "type": "queue_status",
  "data": {
    "queued": 5,
    "running": 2,
    "completed": 3
  }
}
```

**任务状态变化**
```json
{
  "type": "task_status_change",
  "data": {
    "task_id": "queue_xxx",
    "old_status": "queued",
    "new_status": "running"
  }
}
```

**任务进度更新**
```json
{
  "type": "task_progress",
  "data": {
    "task_id": "queue_xxx",
    "progress": 45,
    "message": "Survey 45.00%"
  }
}
```

**任务完成**
```json
{
  "type": "task_completed",
  "data": {
    "task_id": "queue_xxx",
    "result_file": "/path/to/result.xyz",
    "execution_time": 180
  }
}
```

**任务失败**
```json
{
  "type": "task_failed",
  "data": {
    "task_id": "queue_xxx",
    "error_message": "仿真超时"
  }
}
```

---

## 5. 任务状态机

```
                    ┌──────────────┐
                    │   PENDING    │
                    └──────┬───────┘
                           │ submit to queue
                    ┌──────▼───────┐
                ┌───│    QUEUED    │◄──┐
                │   └──────┬───────┘   │ retry
                │          │ schedule  │
                │   ┌──────▼───────┐   │
                │   │   RUNNING    │───┤
                │   └──┬───────┬───┘   │
                │      │       │       │
      pause     │      │       │ fail  │
    ┌───────────┘      │       └───────┼──────┐
    │                  │               │      │
┌───▼──────┐     ┌─────▼──────┐  ┌────▼────┐ │
│  PAUSED  │     │ COMPLETED  │  │ FAILED  │ │
└───┬──────┘     └────────────┘  └─────────┘ │
    │ resume                                  │
    └─────────────────────────────────────────┘
    
    任何状态 ──cancel──> CANCELLED
```

### 状态转换规则

| 当前状态 | 允许的操作 | 目标状态 |
|---------|-----------|---------|
| PENDING | submit | QUEUED |
| QUEUED | start | RUNNING |
| QUEUED | cancel | CANCELLED |
| QUEUED | update_priority | QUEUED |
| RUNNING | complete | COMPLETED |
| RUNNING | fail | FAILED |
| RUNNING | pause | PAUSED |
| RUNNING | cancel | CANCELLED |
| PAUSED | resume | QUEUED |
| PAUSED | cancel | CANCELLED |
| FAILED | retry | QUEUED |
| FAILED | delete | (removed) |

---

## 6. 并发控制策略

### 6.1 信号量机制

```python
class ConcurrencyController:
    def __init__(self, max_concurrent: int):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.running_tasks: Set[str] = set()
    
    async def acquire(self, task_id: str) -> bool:
        await self.semaphore.acquire()
        self.running_tasks.add(task_id)
        return True
    
    def release(self, task_id: str):
        self.running_tasks.discard(task_id)
        self.semaphore.release()
```

### 6.2 调度策略

**优先级 + FIFO**
1. 按优先级排序（高优先级先执行）
2. 同优先级按提交时间排序（FIFO）
3. 考虑任务依赖关系

**资源感知调度**
1. 监控系统资源（CPU、内存）
2. 动态调整并发数
3. 避免系统过载

---

## 7. 持久化设计

### 7.1 SQLite 数据库结构

```sql
-- 任务表
CREATE TABLE tasks (
    task_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    priority INTEGER NOT NULL,
    
    survey_path TEXT NOT NULL,
    output_dir TEXT NOT NULL,
    output_format TEXT NOT NULL,
    
    created_at TIMESTAMP NOT NULL,
    queued_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    progress INTEGER DEFAULT 0,
    message TEXT,
    result_file TEXT,
    error_message TEXT,
    
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    
    metadata TEXT,  -- JSON
    
    INDEX idx_status (status),
    INDEX idx_created_at (created_at),
    INDEX idx_priority (priority)
);

-- 任务依赖表
CREATE TABLE task_dependencies (
    task_id TEXT NOT NULL,
    depends_on_task_id TEXT NOT NULL,
    
    PRIMARY KEY (task_id, depends_on_task_id),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id),
    FOREIGN KEY (depends_on_task_id) REFERENCES tasks(task_id)
);

-- 队列配置表
CREATE TABLE queue_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- 任务日志表
CREATE TABLE task_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    
    FOREIGN KEY (task_id) REFERENCES tasks(task_id),
    INDEX idx_task_id (task_id),
    INDEX idx_timestamp (timestamp)
);
```

### 7.2 持久化策略

- **实时持久化**：任务状态变化立即写入数据库
- **批量日志**：日志批量写入（减少 I/O）
- **定期备份**：自动备份数据库文件
- **启动恢复**：服务重启后恢复未完成任务

---

## 8. 前端 UI 设计

### 8.1 队列监控面板

**组件：QueueMonitorPanel.vue**

**布局：**
```
┌────────────────────────────────────────────┐
│ 队列状态总览                                │
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐       │
│ │ 排队 │ │ 运行 │ │ 完成 │ │ 失败 │       │
│ │  5   │ │  2   │ │ 120  │ │  3   │       │
│ └──────┘ └──────┘ └──────┘ └──────┘       │
├────────────────────────────────────────────┤
│ 任务列表                          [筛选▼]  │
│ ┌──────────────────────────────────────┐  │
│ │ ▶ 任务 #1  [运行中]  ████░░ 45%      │  │
│ │ ⏸ 任务 #2  [已暂停]  ██░░░░ 20%      │  │
│ │ ⏳ 任务 #3  [排队中]  位置: 1         │  │
│ │ ✓ 任务 #4  [已完成]  100%  3分钟前   │  │
│ │ ✗ 任务 #5  [失败]    错误: 超时       │  │
│ └──────────────────────────────────────┘  │
├────────────────────────────────────────────┤
│ 批量操作  [全选] [取消] [重试] [清空]     │
└────────────────────────────────────────────┘
```

**功能：**
- 实时队列状态显示
- 任务列表（可筛选、排序、分页）
- 任务进度条
- 单任务操作（查看、暂停、取消、重试）
- 批量操作
- 自动刷新（WebSocket）

### 8.2 任务提交面板

**组件：TaskSubmitPanel.vue**

**表单：**
- 任务名称
- 优先级选择
- 仿真参数（航迹、模型、配置）
- 高级选项（重试次数、超时时间）
- 任务依赖（可选）

**功能：**
- 快速提交
- 批量提交
- 模板保存

### 8.3 任务详情面板

**组件：TaskDetailPanel.vue**

**内容：**
- 基本信息（ID、名称、状态、优先级）
- 时间信息（创建、开始、完成时间）
- 执行信息（进度、日志、结果）
- 操作按钮（暂停、取消、重试、删除）

---

## 9. 实现要点

### 9.1 核心代码模块

1. **queue_manager.py** - 队列管理器主类
2. **scheduler.py** - 任务调度器
3. **task_storage.py** - 任务持久化
4. **queue_routes.py** - API 路由
5. **queue_websocket.py** - WebSocket 处理

### 9.2 关键算法

**优先级队列排序**
```python
def _sort_key(task: QueuedTask) -> tuple:
    return (-task.priority, task.created_at)
```

**依赖检查**
```python
def can_execute(task: QueuedTask) -> bool:
    for dep_id in task.depends_on:
        dep = get_task(dep_id)
        if dep is None or dep.status != TaskStatus.COMPLETED:
            return False
    return True
```

### 9.3 异常处理

- 任务执行超时：自动终止并标记失败
- 系统资源不足：暂停调度，等待资源释放
- 任务崩溃：记录错误，触发重试
- 数据库错误：降级为内存存储，定期重试

---

## 10. 性能优化

### 10.1 内存优化

- 任务日志限制（只保留最近 1000 条）
- 历史任务归档（完成 > 7 天自动归档）
- 懒加载任务详情

### 10.2 并发优化

- 异步 I/O（asyncio）
- 连接池（数据库）
- 消息批量推送（WebSocket）

### 10.3 监控指标

- 队列长度
- 平均等待时间
- 平均执行时间
- 成功率
- 系统资源使用率

---

## 11. 测试策略

### 11.1 单元测试

- 任务状态转换
- 优先级队列排序
- 并发控制
- 依赖检查

### 11.2 集成测试

- API 端点测试
- WebSocket 通信测试
- 数据库持久化测试

### 11.3 压力测试

- 100+ 任务排队
- 最大并发数测试
- 长时间运行稳定性

---

## 12. 部署建议

### 12.1 生产环境配置

```python
# config.py
QUEUE_CONFIG = {
    "max_concurrent_tasks": 4,
    "max_queue_size": 500,
    "enable_auto_retry": True,
    "retry_delay": 300,
    "task_timeout": 7200,
    "archive_after_days": 30,
    "db_path": "/var/lib/fehals/queue.db"
}
```

### 12.2 监控告警

- 队列积压告警（> 50 个任务）
- 失败率告警（> 10%）
- 系统资源告警（CPU > 90%）

---

## 13. 未来扩展

### 13.1 高级功能

- **任务分组**：按项目/用户分组管理
- **资源预留**：为重要任务预留资源
- **动态优先级**：根据等待时间自动提升优先级
- **任务链**：支持复杂的任务依赖关系（DAG）
- **定时任务**：支持 cron 表达式定时执行
- **分布式队列**：多节点负载均衡

### 13.2 集成扩展

- **Celery 集成**：使用 Celery 作为任务队列后端
- **Redis 集成**：使用 Redis 作为消息队列
- **Kubernetes 集成**：容器化部署和自动扩缩容

---

## 14. 总结

本设计文档提供了一个完整的任务队列管理系统方案，包括：

- ✅ 完整的架构设计
- ✅ 详细的数据模型
- ✅ RESTful API 规范
- ✅ WebSocket 实时通信
- ✅ 任务状态机
- ✅ 并发控制策略
- ✅ 持久化方案
- ✅ 前端 UI 设计
- ✅ 性能优化建议
- ✅ 测试和部署指南

该系统可以有效管理多个 HELIOS++ 仿真任务，提供良好的用户体验和系统稳定性。
