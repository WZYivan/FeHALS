import { defineStore } from 'pinia'
import { useHeliosAPI } from '../composables/useHeliosAPI'
import { useSimulationStore } from './simulation'
import { useSceneStore } from './scene'
import { useWaypointStore } from './waypoints'
import { getPlatform, getScanner } from '../composables/scannerSpecs'

const api = useHeliosAPI()

// 多任务队列 store：调度器配置 + 任务列表 + 轮询
export const useTaskQueueStore = defineStore('taskQueue', {
  state: () => ({
    // 调度器配置
    enabled: false,
    mode: 'sequential', // single | sequential | concurrent
    maxConcurrent: 2,
    paused: false, // 暂停调度：任务只入队不自动启动
    // 统计
    queueSize: 0,
    runningCount: 0,
    totalCount: 0,
    // 任务列表
    tasks: [],
    // 提交中状态（供工具栏和任务队列面板共享）
    submitting: false,
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
        this.paused = res.paused
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
        this.paused = res.paused
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

    async togglePause(paused) {
      return this.updateScheduler({ paused })
    },

    async setMaxConcurrent(n) {
      return this.updateScheduler({ max_concurrent: n })
    },

    // ---- 一键提交当前仿真配置到队列 ----
    // 工具栏「添加到队列」和任务队列面板「添加当前配置到队列」共用此方法，
    // 避免需要两步操作。
    async submitCurrentConfig() {
      if (this.submitting) return
      const simStore = useSimulationStore()
      const sceneStore = useSceneStore()
      const waypointStore = useWaypointStore()

      // 参数校验（与单任务 runSimulation 一致）
      const minAlt = getScanner(simStore.params.scanner_id).params.rangeMin.default
      if (simStore.params.altitude < minAlt) {
        simStore.addLog('ERROR', `飞行高度 ${simStore.params.altitude}m 低于扫描器最小测程 ${minAlt}m，请调高航高或改用更远测程的扫描器`)
        return
      }
      if (!waypointStore.count) {
        simStore.addLog('WARNING', '航点数量为 0，请先添加航点')
        return
      }
      // 多任务模式要求至少一个 OBJ 场景模型，避免无模型时默认地面产生无意义点云
      const objModelIds = sceneStore.models
        .filter((m) => /\.obj$/i.test(m.name))
        .map((m) => m.id)
      if (!objModelIds.length) {
        simStore.addLog('WARNING', '未添加 OBJ 场景模型，多任务模式要求至少一个场景模型，请先上传模型')
        return
      }
      const plat = getPlatform(simStore.params.platform_id)
      const sc = getScanner(simStore.params.scanner_id)
      const allSpecs = { ...plat.params, ...sc.params }
      for (const [key, spec] of Object.entries(allSpecs)) {
        if (spec.readonly) continue
        const val = simStore.params[key]
        if (val < spec.min || val > spec.max) {
          simStore.addLog('ERROR', `${spec.label} 值 ${val} 超出有效范围 [${spec.min}, ${spec.max}]`)
          return
        }
      }

      this.submitting = true
      try {
        // 生成航迹
        const traj = await api.generateTrajectory(waypointStore.points, simStore.params.altitude)
        simStore.addLog('INFO', `航迹生成完成：${traj.file_id}`)
        // 生成配置
        const cfg = await api.generateConfig(simStore.params)
        simStore.addLog('INFO', `配置生成完成：${cfg.config_id}`)
        // 提交到调度器（objModelIds 已在前置校验中确保非空）
        const task = await this.submitTask({
          trajectory_id: traj.file_id,
          config_id: cfg.config_id,
          scene_model_ids: objModelIds,
          name: `${plat.label}-航高${simStore.params.altitude}m`,
        })
        simStore.addLog('INFO', `任务已加入队列：${task.name}（${task.task_id}）`)
      } catch (err) {
        simStore.addLog('ERROR', '加入队列失败：' + (err.response?.data?.detail || err.message))
      } finally {
        this.submitting = false
      }
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
