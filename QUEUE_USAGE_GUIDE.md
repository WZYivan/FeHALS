# 任务队列管理系统使用指南

## 📚 概述

本文档介绍如何使用 FeHALS 的任务队列管理系统。该系统支持多任务顺序执行、并发调度、状态监控等功能。

---

## 📁 文件清单

### 后端文件
```
backend/app/
├── services/
│   └── queue_manager.py          # 队列管理器核心模块
├── api/
│   ├── queue_routes.py           # REST API 路由
│   └── queue_websocket.py        # WebSocket 处理
└── main.py                       # 应用入口（已更新）
```

### 前端文件
```
frontend/src/
└── components/
    └── QueueMonitorPanel.vue     # 队列监控面板
```

### 文档文件
```
FeHALS/
├── QUEUE_SYSTEM_DESIGN.md        # 系统设计文档
└── QUEUE_USAGE_GUIDE.md          # 本使用指南
```

---

## 🚀 快速开始

### 1. 启动后端

后端已自动集成队列管理功能，正常启动即可：

```bash
cd ~/Documents/FeHALS/backend
python run.py
```

启动时会自动：
- 初始化任务队列管理器
- 启动任务调度器
- 开启 WebSocket 状态广播

### 2. 访问 API 文档

打开浏览器访问：
```
http://localhost:8000/docs
```

查看所有队列管理 API 端点。

### 3. 使用前端组件

在 Vue 项目中使用队列监控面板：

```vue
<template>
  <QueueMonitorPanel />
</template>

<script setup>
import QueueMonitorPanel from '@/components/QueueMonitorPanel.vue';
</script>
```

---

## 📖 API 使用示例

### 提交任务到队列

```bash
curl -X POST http://localhost:8000/api/queue/submit \
  -H "Content-Type: application/json" \
  -d '{
    "name": "UAV 扫描任务 #1",
    "priority": 5,
    "survey_path": "/path/to/survey.xml",
    "output_dir": "/path/to/output",
    "output_format": "XYZ"
  }'
```

**响应示例：**
```json
{
  "task_id": "queue_1725436800_abc123",
  "status": "queued",
  "queue_position": 3,
  "estimated_wait_time": 1800,
  "message": "任务已提交到队列"
}
```

### 获取队列状态

```bash
curl http://localhost:8000/api/queue/status
```

**响应示例：**
```json
{
  "total_tasks": 10,
  "queued": 5,
  "running": 2,
  "completed": 3,
  "failed": 0,
  "cancelled": 0,
  "paused": 0,
  "max_concurrent": 2,
  "current_concurrent": 2,
  "queue_length": 5,
  "is_paused": false,
  "queued_tasks": [...],
  "running_tasks": [...]
}
```

### 获取任务列表

```bash
# 获取所有任务
curl http://localhost:8000/api/queue/tasks

# 筛选运行中的任务
curl http://localhost:8000/api/queue/tasks?status=running

# 分页查询
curl http://localhost:8000/api/queue/tasks?limit=20&offset=0
```

### 获取任务详情

```bash
curl http://localhost:8000/api/queue/tasks/queue_1725436800_abc123
```

### 更新任务优先级

```bash
curl -X PATCH http://localhost:8000/api/queue/tasks/queue_xxx/priority \
  -H "Content-Type: application/json" \
  -d '{"priority": 10}'
```

### 取消任务

```bash
curl -X POST http://localhost:8000/api/queue/tasks/queue_xxx/cancel
```

### 重试失败的任务

```bash
curl -X POST http://localhost:8000/api/queue/tasks/queue_xxx/retry
```

### 批量操作

```bash
curl -X POST http://localhost:8000/api/queue/batch \
  -H "Content-Type: application/json" \
  -d '{
    "action": "cancel",
    "task_ids": ["queue_xxx", "queue_yyy", "queue_zzz"]
  }'
```

### 更新队列配置

```bash
curl -X PUT http://localhost:8000/api/queue/config \
  -H "Content-Type: application/json" \
  -d '{
    "max_concurrent_tasks": 4,
    "enable_auto_retry": true,
    "retry_delay": 300
  }'
```

### 暂停/恢复队列

```bash
# 暂停队列调度
curl -X POST http://localhost:8000/api/queue/pause

# 恢复队列调度
curl -X POST http://localhost:8000/api/queue/resume
```

### 获取统计信息

```bash
curl http://localhost:8000/api/queue/statistics
```

---

## 🌐 WebSocket 使用

### 连接 WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/queue');

ws.onopen = () => {
  console.log('WebSocket 已连接');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('收到消息:', message);
  handleMessage(message);
};

ws.onclose = () => {
  console.log('WebSocket 已断开');
};
```

### 消息类型

#### 1. 初始状态
连接后立即收到当前队列状态：
```json
{
  "type": "initial_status",
  "data": {
    "total_tasks": 10,
    "queued": 5,
    "running": 2,
    ...
  }
}
```

#### 2. 队列状态更新（每 5 秒）
```json
{
  "type": "queue_status_update",
  "data": {
    "queued": 5,
    "running": 2,
    ...
  }
}
```

#### 3. 任务入队
```json
{
  "type": "task_queued",
  "task_id": "queue_xxx",
  "name": "任务名称",
  "priority": 5,
  "queue_length": 6
}
```

#### 4. 任务开始
```json
{
  "type": "task_started",
  "task_id": "queue_xxx",
  "name": "任务名称"
}
```

#### 5. 任务进度
```json
{
  "type": "task_progress",
  "task_id": "queue_xxx",
  "progress": 45,
  "message": "Survey 45.00%"
}
```

#### 6. 任务完成
```json
{
  "type": "task_completed",
  "task_id": "queue_xxx",
  "result_file": "/path/to/result.xyz",
  "execution_time": 180
}
```

#### 7. 任务失败
```json
{
  "type": "task_failed",
  "task_id": "queue_xxx",
  "error_message": "仿真超时"
}
```

#### 8. 任务取消
```json
{
  "type": "task_cancelled",
  "task_id": "queue_xxx"
}
```

---

## 🎯 前端使用示例

### Vue 3 示例

#### 使用队列监控面板组件

```vue
<template>
  <div class="app">
    <QueueMonitorPanel />
  </div>
</template>

<script setup>
import QueueMonitorPanel from '@/components/QueueMonitorPanel.vue';
</script>
```

#### 自定义 API 调用

```javascript
import { ref } from 'vue';

const API_BASE = 'http://localhost:8000';

// 提交任务
const submitTask = async (taskData) => {
  const response = await fetch(`${API_BASE}/api/queue/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(taskData),
  });
  return await response.json();
};

// 获取队列状态
const getQueueStatus = async () => {
  const response = await fetch(`${API_BASE}/api/queue/status`);
  return await response.json();
};

// 取消任务
const cancelTask = async (taskId) => {
  const response = await fetch(
    `${API_BASE}/api/queue/tasks/${taskId}/cancel`,
    { method: 'POST' }
  );
  return await response.json();
};

// 使用示例
const onSubmit = async () => {
  try {
    const result = await submitTask({
      name: '测试任务',
      priority: 5,
      survey_path: '/path/to/survey.xml',
      output_dir: '/path/to/output',
      output_format: 'XYZ',
    });
    console.log('任务已提交:', result.task_id);
  } catch (error) {
    console.error('提交失败:', error);
  }
};
```

---

## ⚙️ 配置说明

### 队列配置项

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `max_concurrent_tasks` | int | 2 | 最大并发任务数 |
| `max_queue_size` | int | 100 | 最大队列长度 |
| `enable_auto_retry` | bool | true | 是否自动重试失败任务 |
| `retry_delay` | int | 60 | 重试延迟（秒） |
| `task_timeout` | int | 3600 | 任务超时时间（秒） |

### 任务优先级

| 级别 | 数值 | 说明 |
|------|------|------|
| LOW | 1 | 低优先级 |
| NORMAL | 5 | 普通优先级（默认） |
| HIGH | 10 | 高优先级 |
| URGENT | 20 | 紧急 |

### 任务状态

| 状态 | 说明 |
|------|------|
| `pending` | 待提交 |
| `queued` | 已入队 |
| `running` | 运行中 |
| `paused` | 已暂停 |
| `completed` | 已完成 |
| `failed` | 失败 |
| `cancelled` | 已取消 |

---

## 🔧 高级功能

### 1. 任务依赖

提交任务时指定依赖关系：

```json
{
  "name": "后处理任务",
  "depends_on": ["queue_task1", "queue_task2"],
  ...
}
```

任务会等待所有依赖任务完成后才开始执行。

### 2. 自动重试

失败的任务会自动重试（如果启用）：
- 默认最大重试次数：3 次
- 重试延迟：60 秒（可配置）
- 重试次数达到上限后不再重试

### 3. 优先级调度

队列按优先级排序：
1. 优先级高的任务先执行
2. 同优先级按提交时间排序（FIFO）
3. 可以动态调整任务优先级

### 4. 批量操作

支持批量执行操作：
- 批量取消
- 批量暂停
- 批量恢复
- 批量删除

---

## 📊 监控和统计

### 队列统计指标

- **总任务数**：提交的任务总数
- **完成任务数**：成功完成的任务数
- **失败任务数**：执行失败的任务数
- **成功率**：完成数 / 总数
- **平均执行时间**：任务平均耗时
- **平均等待时间**：任务平均排队时间

### 实时监控

通过 WebSocket 实时监控：
- 队列长度变化
- 任务状态变化
- 任务进度更新
- 系统资源使用

---

## 🐛 故障排除

### 问题 1：任务一直排队不执行

**可能原因：**
- 队列已暂停
- 达到最大并发数
- 任务依赖未满足

**解决方案：**
1. 检查队列是否暂停：`GET /api/queue/status`
2. 检查当前并发数：`current_concurrent < max_concurrent`
3. 检查任务依赖：`GET /api/queue/tasks/{task_id}`

### 问题 2：任务执行失败

**可能原因：**
- 仿真参数错误
- HELIOS++ 路径配置错误
- 资源不足

**解决方案：**
1. 查看任务错误信息：`GET /api/queue/tasks/{task_id}`
2. 检查 HELIOS++ 配置
3. 重试任务：`POST /api/queue/tasks/{task_id}/retry`

### 问题 3：WebSocket 连接失败

**可能原因：**
- 后端未启动
- 端口被占用
- 防火墙阻止

**解决方案：**
1. 确认后端已启动
2. 检查端口 8000 是否可用
3. 检查浏览器控制台错误信息

---

## 📝 开发建议

### 集成到现有工作流

1. **提交任务时使用队列**

   修改原有的直接调用改为队列提交：

   ```python
   # 原来：直接调用
   sim_task = helios_service.run_simulation(...)

   # 现在：提交到队列
   from app.services.queue_manager import get_queue_manager, QueuedTask
   
   manager = get_queue_manager()
   task = QueuedTask(
       task_id=...,
       name=...,
       survey_path=...,
       output_dir=...,
       output_format=...,
       created_at=datetime.now()
   )
   manager.submit_task(task)
   ```

2. **监听任务完成事件**

   通过 WebSocket 监听任务完成：

   ```javascript
   ws.onmessage = (event) => {
     const msg = JSON.parse(event.data);
     if (msg.type === 'task_completed') {
       // 任务完成，执行后续操作
       loadResult(msg.data.result_file);
     }
   };
   ```

3. **添加任务元数据**

   提交任务时添加自定义元数据：

   ```json
   {
     "name": "任务名称",
     "metadata": {
       "user": "admin",
       "project": "project_A",
       "tags": ["测试", "高精度"]
     }
   }
   ```

---

## 🎓 最佳实践

1. **合理设置并发数**
   - 根据服务器性能设置
   - 避免过高导致系统过载
   - 建议：CPU 核心数的 50-75%

2. **使用优先级管理**
   - 紧急任务使用 URGENT
   - 正常任务使用 NORMAL
   - 后台任务使用 LOW

3. **监控队列状态**
   - 定期检查队列积压
   - 关注失败率
   - 及时处理失败任务

4. **定期清理历史**
   - 清空已完成任务
   - 删除失败任务
   - 保持队列整洁

---

## 📚 相关文档

- [系统设计文档](./QUEUE_SYSTEM_DESIGN.md) - 详细的架构设计
- [API 文档](http://localhost:8000/docs) - 完整的 API 参考
- [FeHALS README](./README.md) - 项目总览

---

## 🎉 总结

任务队列管理系统提供了：

✅ **多任务管理** - 支持多任务排队执行  
✅ **并发控制** - 可配置的并发数限制  
✅ **优先级调度** - 灵活的优先级管理  
✅ **实时监控** - WebSocket 实时状态推送  
✅ **自动重试** - 失败任务自动重试  
✅ **批量操作** - 高效的批量任务管理  
✅ **依赖管理** - 支持任务依赖关系  

开始使用吧！🚀
