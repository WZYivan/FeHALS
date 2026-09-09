<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import { useTaskQueueStore } from '../stores/taskQueue'
import { useSimulationStore } from '../stores/simulation'
import { useHeliosAPI } from '../composables/useHeliosAPI'

const emit = defineEmits(['view-task', 'switch-tab'])

const taskStore = useTaskQueueStore()
const simStore = useSimulationStore()
const api = useHeliosAPI()

const modeLabels = {
  single: '单任务阻塞',
  sequential: '顺序执行',
  concurrent: '并发调度',
}

const statusLabels = {
  queued: '排队中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

const statusColors = {
  queued: '#f0ad4e',
  running: '#5bc0de',
  completed: '#5cb85c',
  failed: '#d9534f',
  cancelled: '#999',
}

const sortedTasks = computed(() => {
  // 运行中 > 排队中 > 已完成 > 失败/取消
  const order = { running: 0, queued: 1, completed: 2, failed: 3, cancelled: 4 }
  return [...taskStore.tasks].sort((a, b) => {
    const oa = order[a.status] ?? 9
    const ob = order[b.status] ?? 9
    if (oa !== ob) return oa - ob
    return b.queued_at - a.queued_at
  })
})

async function onToggleEnabled(e) {
  try {
    await taskStore.toggleEnabled(e.target.checked)
    if (e.target.checked) {
      simStore.addLog('INFO', '多任务调度器已启用')
    } else {
      simStore.addLog('INFO', '多任务调度器已关闭，恢复单任务模式')
    }
  } catch (err) {
    simStore.addLog('ERROR', '切换调度器状态失败：' + (err.response?.data?.detail || err.message))
  }
}

async function onModeChange(e) {
  try {
    await taskStore.setMode(e.target.value)
    simStore.addLog('INFO', `调度模式已切换为：${modeLabels[e.target.value]}`)
  } catch (err) {
    simStore.addLog('ERROR', '切换调度模式失败：' + (err.response?.data?.detail || err.message))
  }
}

async function onMaxConcurrentChange(e) {
  const n = Math.max(1, parseInt(e.target.value) || 1)
  try {
    await taskStore.setMaxConcurrent(n)
    simStore.addLog('INFO', `最大并发数已设置为：${n}`)
  } catch (err) {
    simStore.addLog('ERROR', '设置并发数失败：' + (err.response?.data?.detail || err.message))
  }
}

async function addCurrentToQueue() {
  await taskStore.submitCurrentConfig()
}

async function onCancel(taskId) {
  await taskStore.cancelTask(taskId)
  simStore.addLog('INFO', `任务已取消：${taskId}`)
}

async function onRemove(taskId) {
  await taskStore.removeTask(taskId)
}

async function onClearCompleted() {
  await taskStore.clearCompleted()
  simStore.addLog('INFO', '已清空所有已结束任务')
}

async function onViewTask(task) {
  if (task.status !== 'completed') return
  try {
    const res = await api.getResult(task.task_id)
    simStore.taskId = task.task_id
    simStore.status = 'completed'
    simStore.progress = 100
    simStore.result = res
    simStore.addLog('INFO', `已加载任务结果：${task.name}（${res.point_count} 个点）`)
    emit('switch-tab', 'pointcloud')
  } catch (err) {
    simStore.addLog('ERROR', '加载任务结果失败：' + (err.response?.data?.detail || err.message))
  }
}

function fmtTime(ts) {
  if (!ts) return '-'
  return new Date(ts * 1000).toLocaleTimeString()
}

onMounted(() => {
  taskStore.fetchScheduler()
})

onUnmounted(() => {
  taskStore.stopPolling()
})
</script>

<template>
  <section class="panel task-queue-panel">
    <div class="panel-head">
      <h3 class="panel-title">多任务调度</h3>
      <label class="toggle-switch">
        <input type="checkbox" :checked="taskStore.enabled" @change="onToggleEnabled" />
        <span class="toggle-slider"></span>
        <span class="toggle-label">{{ taskStore.enabled ? '已启用' : '已关闭' }}</span>
      </label>
    </div>

    <!-- 未启用时的提示 -->
    <div v-if="!taskStore.enabled" class="task-queue-hint">
      <p>多任务调度器当前<strong>已关闭</strong>，系统使用原有单任务模式。</p>
      <p class="hint-sub">开启后可支持顺序执行、并发调度和任务状态显示。</p>
    </div>

    <!-- 启用后的配置区 -->
    <template v-else>
      <div class="scheduler-config">
        <div class="field">
          <label>调度模式</label>
          <select :value="taskStore.mode" @change="onModeChange">
            <option value="single">单任务阻塞（一次一个）</option>
            <option value="sequential">顺序执行（FIFO 队列）</option>
            <option value="concurrent">并发调度（多任务并行）</option>
          </select>
        </div>
        <div class="field" v-if="taskStore.mode === 'concurrent'">
          <label>最大并发数</label>
          <input
            type="number"
            :value="taskStore.maxConcurrent"
            min="1"
            max="10"
            @change="onMaxConcurrentChange"
          />
        </div>
      </div>

      <!-- 统计 -->
      <div class="task-stats">
        <span class="stat-item stat-queued">排队 {{ taskStore.queueSize }}</span>
        <span class="stat-item stat-running">运行 {{ taskStore.runningCount }}</span>
        <span class="stat-item stat-completed">完成 {{ taskStore.completedTasks.length }}</span>
        <span class="stat-item stat-failed">失败 {{ taskStore.failedTasks.length }}</span>
      </div>

      <!-- 操作按钮 -->
      <div class="task-queue-actions">
        <button class="btn btn-primary btn-sm" :disabled="taskStore.submitting" @click="addCurrentToQueue">
          {{ taskStore.submitting ? '提交中...' : '添加当前配置到队列' }}
        </button>
        <button class="btn btn-sm" @click="onClearCompleted">清空已结束</button>
      </div>

      <!-- 任务列表 -->
      <div class="task-list">
        <div v-if="!sortedTasks.length" class="task-list-empty">暂无任务，点击上方按钮添加</div>
        <div
          v-for="task in sortedTasks"
          :key="task.task_id"
          class="task-item"
          :class="'task-' + task.status"
        >
          <div class="task-item-head">
            <span class="task-name" :title="task.task_id">{{ task.name }}</span>
            <span class="task-status-badge" :style="{ background: statusColors[task.status] }">
              {{ statusLabels[task.status] }}
            </span>
          </div>
          <div class="task-item-meta">
            <span>入队：{{ fmtTime(task.queued_at) }}</span>
            <span v-if="task.started_at">开始：{{ fmtTime(task.started_at) }}</span>
            <span v-if="task.finished_at">结束：{{ fmtTime(task.finished_at) }}</span>
          </div>
          <!-- 进度条 -->
          <div v-if="task.status === 'running' || task.status === 'queued'" class="task-progress-wrap">
            <div class="task-progress-bar">
              <div
                class="task-progress-fill"
                :style="{ width: task.progress + '%', background: statusColors[task.status] }"
              ></div>
            </div>
            <span class="task-progress-text">{{ task.progress }}%</span>
          </div>
          <!-- 消息 -->
          <div v-if="task.message" class="task-message" :class="'msg-' + task.status">
            {{ task.message }}
          </div>
          <!-- 操作按钮 -->
          <div class="task-item-actions">
            <button
              v-if="task.status === 'queued' || task.status === 'running'"
              class="btn btn-danger btn-xs"
              @click="onCancel(task.task_id)"
            >取消</button>
            <button
              v-if="task.status === 'completed'"
              class="btn btn-primary btn-xs"
              @click="onViewTask(task)"
            >查看结果</button>
            <button
              v-if="task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled'"
              class="btn btn-xs"
              @click="onRemove(task.task_id)"
            >移除</button>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>
