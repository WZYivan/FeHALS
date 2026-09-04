import { defineStore } from 'pinia'

// 仿真状态：任务、进度、日志、结果，以及仿真参数配置
export const useSimulationStore = defineStore('simulation', {
  state: () => ({
    taskId: null,
    status: 'idle', // idle | running | completed | failed
    progress: 0,
    message: '',
    result: null, // {file_path, point_count, bounds, points, intensity}
    logs: [], // [{timestamp, level, message}]
    configId: null,
    trajectoryId: null,
    // 覆盖度分析结果：{grid, bounds, statistics}
    coverageResult: null,
    coverageAnalyzing: false,
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
  actions: {
    addLog(level, message) {
      this.logs.push({ timestamp: new Date().toLocaleTimeString(), level, message })
    },
    setCoverageResult(res) {
      this.coverageResult = res
    },
    reset() {
      this.logs = []
      this.progress = 0
      this.status = 'idle'
      this.message = ''
      this.result = null
      this.taskId = null
      this.coverageResult = null
      this.coverageAnalyzing = false
    },
  },
})
