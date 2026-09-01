<script setup>
import { useSceneStore } from '../stores/scene'
import { useThreeScene } from '../composables/useThreeScene'

const sceneStore = useSceneStore()
const three = useThreeScene()

function fmt(v) {
  return Number(v).toFixed(1)
}

function removeModel(id) {
  // 先清理 store，再清理 Three.js 场景（逆序确保即使 Three.js 抛出异常，store 状态也已更新）
  sceneStore.removeModel(id)
  three.removeModel(id)
  // 清除残留的 bbox（Three.js 场景内）
  three.setModelBbox(id, false)
}
</script>

<template>
  <section class="panel model-list">
    <div class="panel-head">
      <h3 class="panel-title">模型列表（{{ sceneStore.models.length }}）</h3>
    </div>

    <ul class="ml-list">
      <li v-for="m in sceneStore.models" :key="m.id">
        <label class="ml-check">
          <input type="checkbox" :checked="m.visible" @change="sceneStore.toggleVisible(m.id); three.setModelVisible(m.id, m.visible)" />
          <span class="ml-name">{{ m.name }}</span>
        </label>
        <label class="ml-check ml-bbox">
          <input type="checkbox" :checked="m.showBbox" @change="sceneStore.toggleBbox(m.id); three.setModelBbox(m.id, m.showBbox)" />
          <span class="ml-bbox-size" v-if="m.bbox">{{ fmt(m.bbox.size[0]) }}×{{ fmt(m.bbox.size[1]) }}×{{ fmt(m.bbox.size[2]) }} m</span>
        </label>
        <button class="ml-del" @click="removeModel(m.id)">×</button>
      </li>
      <li v-if="!sceneStore.models.length" class="ml-empty">暂无模型</li>
    </ul>
  </section>
</template>