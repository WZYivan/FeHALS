<script setup>
import { useSceneStore } from '../stores/scene'
import { useSimulationStore } from '../stores/simulation'

const sceneStore = useSceneStore()
const simStore = useSimulationStore()

function downloadPointCloud() {
  if (!simStore.taskId) return
  const url = `/api/results/${simStore.taskId}/download`
  const a = document.createElement('a')
  a.href = url
  a.download = `fehals_${simStore.taskId}.xyz`
  a.click()
}
</script>

<template>
  <section class="panel pointcloud-panel">
    <h3 class="panel-title">点云渲染属性</h3>

    <div v-if="!simStore.result" class="pc-empty">暂无点云数据，请先执行仿真</div>

    <template v-if="simStore.result">
      <div class="field">
        <label>大小</label>
        <input
          v-model.number="sceneStore.pointOptions.size"
          type="range"
          min="0.01"
          max="1"
          step="0.01"
        />
      </div>

      <div class="field">
        <label>透明度</label>
        <input
          v-model.number="sceneStore.pointOptions.opacity"
          type="range"
          min="0.05"
          max="1"
          step="0.05"
        />
      </div>

      <div class="field">
        <label>着色</label>
        <select v-model="sceneStore.pointOptions.colorMode">
          <option value="height">按高度</option>
          <option value="intensity">按强度</option>
          <option value="fixed">固定颜色</option>
        </select>
      </div>

      <div class="field" v-if="sceneStore.pointOptions.colorMode === 'fixed'">
        <label>颜色</label>
        <input v-model="sceneStore.pointOptions.fixedColor" type="color" />
      </div>

      <button class="btn" style="width: 100%; margin-top: 8px" @click="downloadPointCloud">
        下载点云
      </button>
    </template>
  </section>
</template>