import { defineStore } from 'pinia'
import { useHeliosAPI } from '../composables/useHeliosAPI'

const api = useHeliosAPI()

// 多任务队列 store：调度器配置 + 任务列表 + 轮询
export const useTaskQueueStore = defineStore('taskQueue', {
  state: () => ({
    // 调度器配置
    enabled: false,
    mode: 'sequential', // single | sequential | concurrent
    maxConcurrent: 2,
    // 统计
    queueSize: 0,
    runningCount: 0,
    totalCount: 0,
    // 任务列表
    tasks: [],
    // 轮询
    _pollTimer: null,
    _polling: false,
  }),
  getters: {
    queuedTasks: (s) => s.tasks.filter((t) => t.status === 'queued'),
    runningTasks: (s) => s.tasks.filter((t) => t.status === 'running'),
    completedTasks: (s) => s.tasks.filter((t) => t.status === 'completed'),
    failedTasks: (s) => s.tasks.filter((t) => t.status === 'failed' || t.status === 'cancelled'),
    hasActiveTasks: (s) => s.tasks.some((t) => t.status === 'queued' || t.status === 'running'),
  },
  actions: {
    // ---- 调度器配置 ----
    async fetchScheduler() {
      try {
        const res = await api.getScheduler()
        this.enabled = res.enabled
        this.mode = res.mode
        this.maxConcurrent = res.max_concurrent
        this.queueSize = res.queue_size
        this.runningCount = res.running_count
        this.totalCount = res.total_count
        // 若后端已启用（如刷新页面后），自动开始轮询
        if (this.enabled && !this._polling) {
          this.startPolling()
        }
      } catch (e) {
        console.error('获取调度器配置失败', e)
      }
    },

    async updateScheduler(payload) {
      try {
        const res = await api.updateScheduler(payload)
        this.enabled = res.enabled
        this.mode = res.mode
        this.maxConcurrent = res.max_concurrent
        this.queueSize = res.queue_size
        this.runningCount = res.running_count
        this.totalCount = res.total_count
        // 启用后开始轮询，停用后停止
        if (this.enabled) {
          this.startPolling()
        } else {
          this.stopPolling()
        }
        return res
      } catch (e) {
        console.error('更新调度器配置失败', e)
        throw e
      }
    },

    async toggleEnabled(enabled) {
      return this.updateScheduler({ enabled })
    },

    async setMode(mode) {
      return this.updateScheduler({ mode })
    },

    async setMaxConcurrent(n) {
      return this.updateScheduler({ max_concurrent: n })
    },

    // ---- 任务列表 ----
    async fetchTasks() {
      try {
        const res = await api.listTasks()
        this.tasks = res.tasks || []
        this.queueSize = this.tasks.filter((t) => t.status === 'queued').length
        this.runningCount = this.tasks.filter((t) => t.status === 'running').length
        this.totalCount = this.tasks.length
      } catch (e) {
        console.error('获取任务列表失败', e)
      }
    },

    async submitTask(payload) {
      try {
        const res = await api.submitTask(payload)
        await this.fetchTasks()
        return res
      } catch (e) {
        console.error('提交任务失败', e)
        throw e
      }
    },

    async removeTask(taskId) {
      try {
        await api.removeTask(taskId)
        await this.fetchTasks()
      } catch (e) {
        console.error('移除任务失败', e)
      }
    },

    async clearCompleted() {
      try {
        await api.clearTasks()
        await this.fetchTasks()
      } catch (e) {
        console.error('清空已完成任务失败', e)
      }
    },

    async cancelTask(taskId) {
      try {
        await api.cancelTask(taskId)
        await this.fetchTasks()
      } catch (e) {
        console.error('取消任务失败', e)
      }
    },

    // ---- 轮询 ----
    startPolling() {
      if (this._polling) return
      this._polling = true
      this.fetchTasks()
      this._pollTimer = setInterval(() => {
        this.fetchTasks()
      }, 2000)
    },

    stopPolling() {
      if (this._pollTimer) {
        clearInterval(this._pollTimer)
        this._pollTimer = null
      }
      this._polling = false
    },
  },
})
