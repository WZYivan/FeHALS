<script setup>
import { computed, ref } from 'vue'
import { useSimulationStore } from '../stores/simulation'
import { useHeliosAPI } from '../composables/useHeliosAPI'

const simStore = useSimulationStore()
const api = useHeliosAPI()

const STATUS_TEXT = {
  queued: '排队中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

const cancellingTasks = ref(new Set())

const tasks = computed(() => simStore.taskList)

function select(t) {
  simStore.selectTask(t.taskId)
}

async function cancel(t) {
  if (cancellingTasks.value.has(t.taskId)) return

  // 如果任务已经结束，不发送请求
  if (t.status !== 'queued' && t.status !== 'running') {
    return
  }

  cancellingTasks.value.add(t.taskId)
  try {
    const result = await api.cancelSimulation(t.taskId)
    if (result.success) {
      simStore.addTaskLog(t.taskId, 'INFO', '取消请求已发送')
    } else {
      simStore.addTaskLog(t.taskId, 'WARNING', '取消请求失败：任务可能已结束')
    }
  } catch (err) {
    simStore.addTaskLog(t.taskId, 'ERROR', '取消失败：' + (err.response?.data?.detail || err.message))
  } finally {
    // 无论成功失败，都在短时间后移除禁用状态
    setTimeout(() => cancellingTasks.value.delete(t.taskId), 2000)
  }
}

function isCancelling(taskId) {
  return cancellingTasks.value.has(taskId)
}

function fmtTime(ts) {
  return ts ? new Date(ts * 1000).toLocaleTimeString() : '-'
}
</script>

<template>
  <section class="panel task-queue-panel">
    <div class="panel-head">
      <h3 class="panel-title">任务队列</h3>
      <span class="queue-stats">
        运行 {{ simStore.runningCount }} / 排队 {{ simStore.queuedCount }} /
        并发 {{ simStore.maxConcurrency }}
      </span>
    </div>

    <div v-if="!tasks.length" class="queue-empty">暂无仿真任务</div>

    <ul v-else class="task-list">
      <li
        v-for="t in tasks"
        :key="t.taskId"
        class="task-item"
        :class="{ active: t.taskId === simStore.selectedTaskId }"
        @click="select(t)"
      >
        <span class="task-badge" :class="'status-' + t.status">
          {{ STATUS_TEXT[t.status] || t.status }}
        </span>
        <div class="task-body">
          <span class="task-id">{{ t.taskId }}</span>
          <div class="task-progress-row" v-if="t.status === 'running' || t.status === 'queued'">
            <progress :value="t.progress || 0" max="100"></progress>
            <span class="task-percent">{{ t.progress || 0 }}%</span>
          </div>
          <div class="task-message" v-if="t.message">{{ t.message }}</div>
          <span class="task-meta">{{ fmtTime(t.submitted_at) }}</span>
        </div>
        <button
          v-if="t.status === 'queued' || t.status === 'running'"
          class="btn btn-sm"
          :disabled="isCancelling(t.taskId)"
          @click.stop="cancel(t)"
        >
          {{ isCancelling(t.taskId) ? '取消中...' : '取消' }}
        </button>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.task-queue-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.queue-stats {
  font-size: 12px;
  color: #888;
}
.queue-empty {
  padding: 24px;
  text-align: center;
  color: #aaa;
}
.task-list {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
}
.task-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-bottom: 1px solid #eee;
  cursor: pointer;
}
.task-item:hover {
  background: #f5f7fa;
}
.task-item.active {
  background: #eef4ff;
}
.task-badge {
  flex-shrink: 0;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  color: #fff;
}
.status-queued {
  background: #909399;
}
.status-running {
  background: #409eff;
}
.status-completed {
  background: #67c23a;
}
.status-failed {
  background: #f56c6c;
}
.status-cancelled {
  background: #c0c4cc;
}
.task-body {
  flex: 1;
  min-width: 0;
}
.task-id {
  font-size: 12px;
  font-family: monospace;
}
.task-progress-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 4px 0;
}
.task-progress-row progress {
  flex: 1;
  height: 8px;
  border-radius: 4px;
  overflow: hidden;
}
.task-progress-row progress::-webkit-progress-bar {
  background-color: #e5e7eb;
  border-radius: 4px;
}
.task-progress-row progress::-webkit-progress-value {
  background: linear-gradient(90deg, #409eff 0%, #66b1ff 100%);
  border-radius: 4px;
  transition: width 0.3s ease;
}
.task-progress-row progress::-moz-progress-bar {
  background: linear-gradient(90deg, #409eff 0%, #66b1ff 100%);
  border-radius: 4px;
}
.task-percent {
  font-size: 12px;
  font-weight: 600;
  color: #409eff;
  min-width: 40px;
  text-align: right;
}
.task-message {
  font-size: 11px;
  color: #666;
  margin: 2px 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.task-meta {
  font-size: 11px;
  color: #aaa;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
