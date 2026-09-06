<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useSceneStore } from './stores/scene'
import { useWaypointStore } from './stores/waypoints'
import { useSimulationStore } from './stores/simulation'
import { useHeliosAPI, connectQueueWS } from './composables/useHeliosAPI'
import { useThreeScene } from './composables/useThreeScene'
import { generateBowtie } from './composables/useBowtie'
import { getParams } from './composables/scannerSpecs'
import Scene3D from './components/Scene3D.vue'
import ControlPanel from './components/ControlPanel.vue'
import WaypointList from './components/WaypointList.vue'
import PointCloudPanel from './components/PointCloudPanel.vue'
import ModelList from './components/ModelList.vue'
import SettingsPanel from './components/SettingsPanel.vue'
import LogConsole from './components/LogConsole.vue'
import TaskQueuePanel from './components/TaskQueuePanel.vue'

const sceneStore = useSceneStore()
const waypointStore = useWaypointStore()
const simStore = useSimulationStore()
const api = useHeliosAPI()
const three = useThreeScene()

const fileInput = ref(null)
const activeTab = ref('params')

// 可调布局
const sidebarWidth = ref(320)
const consoleHeight = ref(200)

function startSidebarResize(e) {
  e.preventDefault()
  const startX = e.clientX
  const startW = sidebarWidth.value
  const onMove = (ev) => {
    sidebarWidth.value = Math.min(600, Math.max(200, startW - (ev.clientX - startX)))
  }
  const onUp = () => {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
    document.body.style.cursor = ''
  }
  document.body.style.cursor = 'col-resize'
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

function startConsoleResize(e) {
  e.preventDefault()
  const startY = e.clientY
  const startH = consoleHeight.value
  const onMove = (ev) => {
    consoleHeight.value = Math.min(500, Math.max(80, startH - (ev.clientY - startY)))
  }
  const onUp = () => {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
    document.body.style.cursor = ''
  }
  document.body.style.cursor = 'row-resize'
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

const statusText = {
  idle: '就绪',
  queued: '排队中',
  running: '仿真中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

// 模型上传
function onPickModel() {
  fileInput.value && fileInput.value.click()
}

async function onFileChange(e) {
  const file = e.target.files && e.target.files[0]
  e.target.value = ''
  if (!file) return
  simStore.addLog('INFO', `开始上传模型：${file.name}`)
  try {
    const res = await api.uploadModel(file)
    sceneStore.addModel({ id: res.model_id, name: res.filename, url: res.url, up: res.up || 'z' })
    simStore.addLog('INFO', `模型上传完成：${res.filename}`)
  } catch (err) {
    simStore.addLog('ERROR', '模型上传失败：' + (err.response?.data?.detail || err.message))
  }
}

// 导出航迹
async function exportTrajectory() {
  if (!waypointStore.count) {
    simStore.addLog('WARNING', '航点数量为 0，请先在场景中点击添加航点')
    return
  }
  try {
    const res = await api.generateTrajectory(waypointStore.points, simStore.params.altitude)
    simStore.trajectoryId = res.file_id
    simStore.addLog('INFO', `航迹已导出：${res.file_id}（${res.point_count} 个航点）`)
  } catch (err) {
    simStore.addLog('ERROR', '航迹导出失败：' + (err.response?.data?.detail || err.message))
  }
}

// 弓字形
let bowtieCorners = []

function startBowtie() {
  bowtieCorners = []
  sceneStore.pickMode = 'rect'
  activeTab.value = 'trajectory'
  three.setPickMode('rect', (p) => {
    bowtieCorners.push(p)
    if (bowtieCorners.length >= 2) {
      const pts = generateBowtie(bowtieCorners[0], bowtieCorners[1], simStore.params.line_spacing)
      pts.forEach((p) => waypointStore.add(p))
      simStore.addLog('INFO', `弓字形航迹生成：${pts.length} 个航点（间距 ${simStore.params.line_spacing}m）`)
      bowtieCorners = []
      sceneStore.pickMode = 'waypoint'
      three.setPickMode('waypoint', null)
    }
  })
  simStore.addLog('INFO', '请点击两个角点定义矩形区域')
}

// 执行仿真（提交任务入队）
async function runSimulation() {
  const minAlt = getParams(simStore.params.platform_type).scanner.params.rangeMin.default
  if (simStore.params.altitude < minAlt) {
    simStore.addLog('ERROR', `飞行高度 ${simStore.params.altitude}m 低于 ${simStore.params.platform_type} 平台最小测程 ${minAlt}m，请调高航高或改用 UAV 平台`)
    return
  }
  if (!waypointStore.count) {
    simStore.addLog('WARNING', '航点数量为 0，请先添加航点')
    return
  }
  // 参数范围校验
  const specs = getParams(simStore.params.platform_type)
  const allSpecs = { ...specs.platform.params, ...specs.scanner.params }
  for (const [key, spec] of Object.entries(allSpecs)) {
    if (spec.readonly) continue
    const val = simStore.params[key]
    if (val < spec.min || val > spec.max) {
      simStore.addLog('ERROR', `${spec.label} (${spec.unit}) 值 ${val} 超出有效范围 [${spec.min}, ${spec.max}]`)
      return
    }
  }
  simStore.reset()
  try {
    const traj = await api.generateTrajectory(waypointStore.points, simStore.params.altitude)
    simStore.trajectoryId = traj.file_id
    simStore.addLog('INFO', `航迹生成完成：${traj.file_id}`)

    const cfg = await api.generateConfig(simStore.params)
    simStore.configId = cfg.config_id
    simStore.addLog('INFO', `配置生成完成：${cfg.config_id}`)

    const run = await api.runSimulation({
      trajectory_id: traj.file_id,
      config_id: cfg.config_id,
      scene_model_id: sceneStore.activeModelId || null,
    })
    simStore.upsertTask({
      task_id: run.task_id,
      status: run.status || 'queued',
      progress: 0,
      message: '',
      output_format: simStore.params.output_format,
      submitted_at: Date.now() / 1000,
    })
    simStore.selectTask(run.task_id)
    simStore.addLog('INFO', `仿真任务已提交：${run.task_id}（${run.status === 'queued' ? '排队中' : run.status}）`)
  } catch (err) {
    simStore.addLog('ERROR', '仿真启动失败：' + (err.response?.data?.detail || err.message))
  }
}

async function cancelSimulation() {
  const taskId = simStore.selectedTaskId
  if (!taskId) return
  try {
    await api.cancelSimulation(taskId)
    simStore.addLog('INFO', '已发送取消请求')
  } catch (err) {
    simStore.addLog('ERROR', '取消失败：' + (err.response?.data?.detail || err.message))
  }
}

function downloadPointCloud() {
  if (!simStore.taskId) return
  const url = `/api/results/${simStore.taskId}/download`
  const a = document.createElement('a')
  a.href = url
  a.download = `fehals_${simStore.taskId}.xyz`
  a.click()
}

function handleQueueMessage(msg) {
  simStore.handleQueueEvent(msg)
  if (msg.type === 'complete' && msg.task_id) {
    loadResult(msg.task_id)
  }
}

async function loadResult(taskId) {
  try {
    const res = await api.getResult(taskId)
    const t = simStore.tasks[taskId]
    if (t) t.result = res
    if (simStore.selectedTaskId === taskId) simStore.result = res
    simStore.addTaskLog(taskId, 'INFO', `点云加载完成：${res.point_count} 个点`)
  } catch (err) {
    simStore.addTaskLog(taskId, 'ERROR', '结果加载失败：' + (err.response?.data?.detail || err.message))
  }
}

let queueWs = null
let queueReconnectTimer = null
let queueReconnectAttempts = 0

function connectQueue() {
  queueWs = connectQueueWS({
    onOpen: () => {
      queueReconnectAttempts = 0
      simStore.addLog('INFO', '任务队列通道已连接')
    },
    onMessage: (msg) => handleQueueMessage(msg),
    onClose: () => scheduleQueueReconnect(),
    onError: () => simStore.addLog('WARNING', '任务队列通道连接出错，尝试重连...'),
  })
}

// 指数退避自动重连（后端重启 / 网络抖动时保证状态不永久失联）
function scheduleQueueReconnect() {
  if (queueReconnectTimer) return
  const delay = Math.min(1000 * 2 ** queueReconnectAttempts, 15000)
  queueReconnectAttempts += 1
  queueReconnectTimer = setTimeout(() => {
    queueReconnectTimer = null
    connectQueue()
  }, delay)
}

onMounted(() => {
  connectQueue()
  startQueuePolling()
})
onUnmounted(() => {
  if (queueReconnectTimer) clearTimeout(queueReconnectTimer)
  if (queueWs) queueWs.close()
  stopQueuePolling()
})

// ---- 轮询兜底：即使 /ws/queue 不可用，也每 2s 拉一次后端队列快照同步状态/进度 ----
let queuePollTimer = null

function startQueuePolling() {
  if (queuePollTimer) return
  const tick = async () => {
    try {
      const snap = await api.getQueue()
      simStore.applySnapshot(snap)
    } catch (err) {
      // 后端暂不可用时静默，等下一次轮询
    }
  }
  queuePollTimer = setInterval(tick, 2000)
  tick()
}

function stopQueuePolling() {
  if (queuePollTimer) {
    clearInterval(queuePollTimer)
    queuePollTimer = null
  }
}
</script>

<template>
  <div class="app">
    <header class="toolbar">
      <span class="brand">FeHALS</span>
      <span class="brand-sub">3D 可视化航路规划与激光仿真</span>
      <div class="toolbar-actions">
        <input
          ref="fileInput"
          type="file"
          accept=".obj,.gltf,.glb,.stl"
          style="display: none"
          @change="onFileChange"
        />
        <button class="btn" @click="onPickModel">模型上传</button>
        <button class="btn" @click="exportTrajectory">导出航迹</button>
        <button class="btn btn-primary" @click="runSimulation">执行仿真</button>
        <button
          class="btn btn-danger"
          @click="cancelSimulation"
          v-if="simStore.selectedTask && (simStore.selectedTask.status === 'queued' || simStore.selectedTask.status === 'running')"
        >取消</button>
        <span class="status-badge" :class="'status-' + simStore.status">
          {{ statusText[simStore.status] || simStore.status }}
          <template v-if="simStore.status === 'running'"> {{ simStore.progress }}%</template>
        </span>
      </div>
    </header>

    <div class="main">
      <div class="scene-area">
        <Scene3D />
      </div>
      <div class="resizer-v" @mousedown="startSidebarResize"></div>
      <aside class="sidebar" :style="{ width: sidebarWidth + 'px' }">
        <div class="tabs">
          <button :class="{ active: activeTab === 'params' }" @click="activeTab = 'params'">仿真参数</button>
          <button :class="{ active: activeTab === 'queue' }" @click="activeTab = 'queue'">任务队列</button>
          <button :class="{ active: activeTab === 'pointcloud' }" @click="activeTab = 'pointcloud'">点云</button>
          <button :class="{ active: activeTab === 'models' }" @click="activeTab = 'models'">模型列表</button>
          <button :class="{ active: activeTab === 'trajectory' }" @click="activeTab = 'trajectory'">航迹</button>
          <button :class="{ active: activeTab === 'settings' }" @click="activeTab = 'settings'">设置</button>
        </div>
        <ControlPanel v-if="activeTab === 'params'" />
        <TaskQueuePanel v-if="activeTab === 'queue'" />
        <PointCloudPanel v-if="activeTab === 'pointcloud'" />
        <ModelList v-if="activeTab === 'models'" />
        <template v-if="activeTab === 'trajectory'">
          <section class="panel bowtie-panel">
            <h3 class="panel-title">弓字形航线</h3>
            <div class="field">
              <label>间距 (m)</label>
              <input v-model.number="simStore.params.line_spacing" type="number" step="1" min="1" />
            </div>
            <button class="btn" style="width: 100%" @click="startBowtie">弓字形航线</button>
            <p class="bowtie-hint">点击场景中两点定义矩形区域，自动生成弓字形航线</p>
          </section>
          <WaypointList />
        </template>
        <SettingsPanel v-if="activeTab === 'settings'" />
      </aside>
    </div>

    <div class="resizer-h" @mousedown="startConsoleResize"></div>
    <LogConsole class="console" :style="{ height: consoleHeight + 'px' }" />
  </div>
</template>
