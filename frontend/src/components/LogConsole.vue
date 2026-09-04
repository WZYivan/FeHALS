<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useSimulationStore } from '../stores/simulation'

const simStore = useSimulationStore()
const box = ref(null)

const selectedId = computed({
  get: () => simStore.selectedTaskId,
  set: (v) => simStore.selectTask(v || null),
})

const tasks = computed(() => simStore.taskList)

// 自动滚动到底部
watch(
  () => simStore.logs.length,
  async () => {
    await nextTick()
    if (box.value) box.value.scrollTop = box.value.scrollHeight
  }
)

function clear() {
  simStore.clearLogs()
}
</script>

<template>
  <section class="panel log-console">
    <div class="panel-head">
      <h3 class="panel-title">日志控制台</h3>
      <select v-model="selectedId" class="log-task-select">
        <option :value="null">全局日志</option>
        <option v-for="t in tasks" :key="t.taskId" :value="t.taskId">
          {{ t.taskId }}
        </option>
      </select>
      <button class="btn btn-sm" @click="clear">清空</button>
    </div>
    <div ref="box" class="log-box">
      <div v-for="(l, i) in simStore.logs" :key="i" class="log-line" :class="'log-' + l.level.toLowerCase()">
        <span class="log-time">[{{ l.timestamp }}]</span>
        <span class="log-level">{{ l.level }}</span>
        <span class="log-msg">{{ l.message }}</span>
      </div>
      <div v-if="!simStore.logs.length" class="log-empty">暂无日志</div>
    </div>
  </section>
</template>

<style scoped>
.panel-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.panel-title {
  margin-right: auto;
}
.log-task-select {
  max-width: 220px;
  padding: 2px 6px;
  font-size: 12px;
}
</style>
