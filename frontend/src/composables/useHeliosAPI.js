import axios from 'axios'

// 后端 REST API 客户端（经 Vite 代理到 FastAPI）
const api = axios.create({ baseURL: '/api' })

export function useHeliosAPI() {
  // ---- 模型 ----
  const uploadModel = (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post('/models/upload', fd).then((r) => r.data)
  }
  // 批量上传：各文件独立 POST，一个失败不影响其余；返回 {ok: [...], fail: [...]}
  const uploadModels = async (files) => {
    const results = await Promise.allSettled(files.map((f) => uploadModel(f)))
    const ok = [], fail = []
    results.forEach((r, i) => {
      if (r.status === 'fulfilled') ok.push(r.value)
      else fail.push({ name: files[i].name, error: r.reason?.response?.data?.detail || r.reason?.message })
    })
    return { ok, fail }
  }
  const listModels = () => api.get('/models').then((r) => r.data)
  const deleteModel = (id) => api.delete(`/models/${id}`).then((r) => r.data)

  // ---- 航迹 ----
  const generateTrajectory = (waypoints, altitude) =>
    api
      .post('/trajectory/generate', {
        waypoints: waypoints.map((p) => [p.x, p.y, p.z]),
        altitude,
      })
      .then((r) => r.data)
  const listTrajectories = () => api.get('/trajectories').then((r) => r.data)

  // ---- 配置 ----
  const generateConfig = (params) => api.post('/config/generate', params).then((r) => r.data)

  // ---- 仿真 ----
  const runSimulation = (payload) => api.post('/simulation/run', payload).then((r) => r.data)
  const getStatus = (id) => api.get(`/simulation/status/${id}`).then((r) => r.data)
  const getLogs = (id) => api.get(`/simulation/logs/${id}`).then((r) => r.data)
  const cancelSimulation = (id) => api.post(`/simulation/cancel/${id}`).then((r) => r.data)

  // ---- 结果 ----
  const getResult = (id) => api.get(`/results/${id}`).then((r) => r.data)

  // ---- 覆盖度分析 ----
  const analyzeCoverage = (points, gridSize = 50) =>
    api.post('/coverage/analyze', { points, grid_size: gridSize }).then((r) => r.data)

  // ---- 缓存 ----
  const listCache = () => api.get('/cache').then((r) => r.data)
  const clearCache = (type) => api.delete(`/cache/${type}`).then((r) => r.data)

  // ---- 环境诊断 ----
  const diagnoseEnv = () => api.get('/env/diagnose').then((r) => r.data)

  // ---- 多任务调度器 ----
  const getScheduler = () => api.get('/scheduler').then((r) => r.data)
  const updateScheduler = (payload) => api.put('/scheduler', payload).then((r) => r.data)
  const listTasks = () => api.get('/tasks').then((r) => r.data)
  const submitTask = (payload) => api.post('/tasks', payload).then((r) => r.data)
  const submitBatchTasks = (tasks) => api.post('/tasks/batch', { tasks }).then((r) => r.data)
  const removeTask = (id) => api.delete(`/tasks/${id}`).then((r) => r.data)
  const clearTasks = () => api.post('/tasks/clear').then((r) => r.data)
  const cancelTask = (id) => api.post(`/tasks/${id}/cancel`).then((r) => r.data)

  return {
    uploadModel,
    uploadModels,
    listModels,
    deleteModel,
    generateTrajectory,
    listTrajectories,
    generateConfig,
    runSimulation,
    getStatus,
    getLogs,
    cancelSimulation,
    getResult,
    analyzeCoverage,
    listCache,
    clearCache,
    diagnoseEnv,
    getScheduler,
    updateScheduler,
    listTasks,
    submitTask,
    submitBatchTasks,
    removeTask,
    clearTasks,
    cancelTask,
  }
}

// WebSocket 日志连接：WS /ws/logs/{task_id}
export function connectLogWS(taskId, handlers = {}) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${location.host}/ws/logs/${taskId}`)
  ws.onopen = () => handlers.onOpen && handlers.onOpen()
  ws.onmessage = (e) => {
    let msg
    try {
      msg = JSON.parse(e.data)
    } catch {
      return
    }
    handlers.onMessage && handlers.onMessage(msg)
  }
  ws.onclose = () => handlers.onClose && handlers.onClose()
  ws.onerror = (err) => handlers.onError && handlers.onError(err)
  return ws
}
