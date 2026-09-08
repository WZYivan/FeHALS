import { defineStore } from 'pinia'

// 状态单调等级：消息可能乱序（旧版后端竞态/重连），低等级不覆盖高等级。
// queued(0) -> running(1) -> 终态(2)。终态与运行态不会被迟到的 queued 降级。
const STATUS_RANK = { queued: 0, running: 1, completed: 2, failed: 2, cancelled: 2 }

export const useSimulationStore = defineStore('simulation', {
  state: () => ({
    // ---- 多任务队列 ----
    tasks: {}, // taskId -> { taskId, status, progress, message, result, result_file, submitted_at, logs: [] }
    order: [], // 任务提交顺序（taskId 列表）
    selectedTaskId: null, // null = 全局日志视图
    maxConcurrency: 1,
    globalLogs: [], // 全局日志（模型上传、航迹导出、配置生成等）

    // ---- 兼容旧字段（当前选中任务的视图状态）----
    taskId: null,
    status: 'idle', // idle | queued | running | completed | failed | cancelled
    progress: 0,
    message: '',
    result: null, // {file_path, point_count, bounds, points, intensity}
    logs: [], // 当前视图日志（选中任务或全局）
    configId: null,
    trajectoryId: null,

    // 仿真参数（与 ControlPanel 表单双向绑定）
    params: {
      platform_type: 'UAV',
      speed: 5.0,
      altitude: 100.0,
      scan_freq: 10.0,
      scan_angle: 30.0,
      pulse_freq: 50.0,
      // 默认 XYZ：本机 helios++ 构建的 LAS 输出不可用，见 README
      output_format: 'XYZ',
      line_spacing: 10.0, // 弓字形航线间距 (m)
    },
  }),
  getters: {
    selectedTask(state) {
      return state.selectedTaskId ? state.tasks[state.selectedTaskId] : null
    },
    taskList(state) {
      return state.order.map((id) => state.tasks[id]).filter(Boolean)
    },
    // 实时统计（由 tasks 推导，避免事件乱序导致的计数漂移）
    runningCount(state) {
      return state.order.reduce(
        (n, id) => n + (state.tasks[id] && state.tasks[id].status === 'running' ? 1 : 0),
        0
      )
    },
    queuedCount(state) {
      return state.order.reduce(
        (n, id) => n + (state.tasks[id] && state.tasks[id].status === 'queued' ? 1 : 0),
        0
      )
    },
  },
  actions: {
    _ensure(taskId) {
      if (!this.tasks[taskId]) {
        this.tasks[taskId] = {
          taskId,
          status: 'queued',
          progress: 0,
          message: '',
          result: null,
          result_file: null,
          submitted_at: null,
          logs: [],
        }
        this.order.push(taskId)
      }
      return this.tasks[taskId]
    },

    upsertTask(brief) {
      const t = this._ensure(brief.task_id)
      // 单调推进：低等级消息不覆盖高等级状态
      const newStatus = brief.status
      if (newStatus && (STATUS_RANK[newStatus] ?? -1) >= (STATUS_RANK[t.status] ?? -1)) {
        t.status = newStatus
      }
      if (brief.progress != null) t.progress = brief.progress
      if (brief.message != null) t.message = brief.message
      if (brief.result_file != null) t.result_file = brief.result_file
      if (brief.submitted_at != null) t.submitted_at = brief.submitted_at
      if (this.selectedTaskId === t.taskId) this._syncSelected()
    },

    selectTask(taskId) {
      this.selectedTaskId = taskId || null
      if (taskId) {
        const t = this._ensure(taskId)
        this.logs = t.logs
      } else {
        this.logs = this.globalLogs
      }
      this._syncSelected()
    },

    _syncSelected() {
      const t = this.selectedTaskId ? this.tasks[this.selectedTaskId] : null
      if (t) {
        this.taskId = t.taskId
        this.status = t.status
        this.progress = t.progress
        this.message = t.message
        this.result = t.result
      } else {
        this.taskId = null
        this.status = 'idle'
        this.progress = 0
        this.message = ''
        this.result = null
      }
    },

    // 兼容旧调用：写入当前视图（选中任务或全局）
    addLog(level, message) {
      const entry = { timestamp: new Date().toLocaleTimeString(), level, message }
      if (this.selectedTaskId) {
        const t = this._ensure(this.selectedTaskId)
        t.logs.push(entry)
        this.logs = t.logs
      } else {
        this.globalLogs.push(entry)
        this.logs.push(entry)
      }
    },

    // 写入指定任务的日志（不受当前选中影响）
    addTaskLog(taskId, level, message) {
      const t = this._ensure(taskId)
      t.logs.push({ timestamp: new Date().toLocaleTimeString(), level, message })
      if (taskId === this.selectedTaskId) this.logs = t.logs
    },

    applySnapshot(snap) {
      this.maxConcurrency = snap.max_concurrency
      // 后端快照是全量权威：清理后端已不存在的本地任务（幽灵），避免残留"运行中 0%"
      const keep = new Set(snap.tasks.map((b) => b.task_id))
      for (const id of Object.keys(this.tasks)) {
        if (!keep.has(id)) {
          delete this.tasks[id]
          if (this.selectedTaskId === id) this.selectedTaskId = null
        }
      }
      // 顺序以服务器为准
      this.order = [...keep]
      for (const brief of snap.tasks) this.upsertTask(brief)
      if (!this.selectedTaskId && this.order.length) this.selectTask(this.order[0])
      if (this.selectedTaskId) this._syncSelected()
    },

    handleQueueEvent(msg) {
      if (msg.type === 'snapshot') return this.applySnapshot(msg)

      const taskId = msg.task_id
      if (taskId) {
        const t = this._ensure(taskId)
        // 先应用消息自带的完整 task 摘要（rank 单调推进）
        if (msg.task) this.upsertTask(msg.task)

        if (msg.type === 'task_started') {
          // 显式推进为运行态（rank 已保证不降级终态）
          this.upsertTask({ task_id: taskId, status: 'running' })
        } else if (msg.type === 'task_finished') {
          if (msg.task) {
            this.upsertTask({
              task_id: taskId,
              status: msg.task.status,
              message: msg.task.message,
              progress: msg.task.progress,
              result_file: msg.task.result_file,
            })
          }
        } else if (msg.type === 'task_cancelled') {
          this.upsertTask({ task_id: taskId, status: 'cancelled', message: '已取消' })
        } else if (msg.type === 'progress') {
          if (msg.percent != null) t.progress = msg.percent
        } else if (msg.type === 'log') {
          t.logs.push({
            timestamp: msg.timestamp || new Date().toLocaleTimeString(),
            level: msg.level || 'INFO',
            message: msg.message,
          })
        } else if (msg.type === 'error') {
          if (msg.message) {
            t.message = msg.message
            t.logs.push({
              timestamp: msg.timestamp || new Date().toLocaleTimeString(),
              level: 'ERROR',
              message: msg.message,
            })
          }
        } else if (msg.type === 'complete') {
          this.upsertTask({
            task_id: taskId,
            status: 'completed',
            progress: 100,
            result_file: msg.result_file,
            message: msg.message || '仿真完成',
          })
        }
      }
      if (this.selectedTaskId) this._syncSelected()
    },

    clearLogs() {
      if (this.selectedTaskId) {
        const t = this.tasks[this.selectedTaskId]
        if (t) {
          t.logs = []
          this.logs = t.logs
        }
      } else {
        this.globalLogs = []
        this.logs = this.globalLogs
      }
    },

    reset() {
      // 兼容旧调用：重置为全局视图（不清空任务列表）
      this.selectTask(null)
      this.globalLogs = []
      this.logs = this.globalLogs
      this.status = 'idle'
      this.progress = 0
      this.message = ''
      this.result = null
      this.taskId = null
    },
  },
})
