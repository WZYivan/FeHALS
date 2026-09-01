<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useThreeScene } from '../composables/useThreeScene'
import { useWaypoints } from '../composables/useWaypoints'
import { useSceneStore } from '../stores/scene'
import { useWaypointStore } from '../stores/waypoints'
import { useSimulationStore } from '../stores/simulation'

const three = useThreeScene()
const waypoints = useWaypoints()
const sceneStore = useSceneStore()
const waypointStore = useWaypointStore()
const simStore = useSimulationStore()

const container = ref(null)
const loadedIds = new Set()

onMounted(() => {
  three.init(container.value)

  waypoints.setCallbacks({
    onAdd: (p) => waypointStore.add(p),
    onMove: (index, p) => waypointStore.update(index, p),
    onRemove: (index) => waypointStore.remove(index),
  })
  waypoints.renderWaypoints(waypointStore.points)
})

onBeforeUnmount(() => {
  three.dispose()
})

// store 航点变化 → 重建三维表示
watch(
  () => waypointStore.points,
  (points) => waypoints.renderWaypoints(points),
  { deep: true }
)

// 模型变化 → 加载到场景，或从场景移除
watch(
  () => sceneStore.models.map((m) => m.id),
  (ids) => {
    // 移除已加载但 store 中不再存在的模型
    for (const id of loadedIds) {
      if (!ids.includes(id)) {
        three.removeModel(id)
        loadedIds.delete(id)
      }
    }
    // 加载新模型
    sceneStore.models.forEach((m) => {
      if (loadedIds.has(m.id)) return
      loadedIds.add(m.id)
      sceneStore.setLoading(true)
      three
        .loadModel(m.url, m.name, m.up, m.id)
        .then(({ size }) => {
          sceneStore.setLoading(false)
          sceneStore.setModelBbox(m.id, { size })
        })
        .catch((err) => {
          sceneStore.setLoading(false)
          simStore.addLog('ERROR', `模型加载失败（${m.name}）：${err.message || err}`)
        })
    })
  },
  { deep: true }
)

// 模型可见性
watch(
  () => sceneStore.models.map((m) => ({ id: m.id, visible: m.visible })),
  (vals) => vals.forEach((v) => three.setModelVisible(v.id, v.visible)),
  { deep: true }
)

// 模型 bbox
watch(
  () => sceneStore.models.map((m) => ({ id: m.id, showBbox: m.showBbox })),
  (vals) => vals.forEach((v) => three.setModelBbox(v.id, v.showBbox)),
  { deep: true }
)

// 仿真结果 → 点云渲染
watch(
  () => simStore.result,
  (result) => {
    if (result) three.setPointCloud(result.points, result.intensity, sceneStore.pointOptions)
  }
)

// 点云渲染参数 → 实时更新
watch(
  () => sceneStore.pointOptions,
  (opts) => three.updatePointCloud(opts),
  { deep: true }
)
</script>

<template>
  <div class="scene3d">
    <div ref="container" class="scene-container"></div>

    <div v-if="sceneStore.loading" class="loading-overlay">
      <div class="spinner"></div>
      <span>模型加载中...</span>
    </div>
  </div>
</template>