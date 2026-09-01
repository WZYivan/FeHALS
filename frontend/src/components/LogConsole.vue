<script setup>
import { nextTick, ref, watch } from 'vue'
import { useSimulationStore } from '../stores/simulation'

const simStore = useSimulationStore()
const box = ref(null)

// 自动滚动到底部
watch(
  () => simStore.logs.length,
  async () => {
    await nextTick()
    if (box.value) box.value.scrollTop = box.value.scrollHeight
  }
)

function clear() {
  simStore.logs = []
}
</script>

<template>
  <section class="panel log-console">
    <div class="panel-head">
      <h3 class="panel-title">日志控制台</h3>
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
