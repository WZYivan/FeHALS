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

  return {
    uploadModel,
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
