<script setup>
import { useWaypointStore } from '../stores/waypoints'

const waypointStore = useWaypointStore()

function fmt(v) {
  return Number(v).toFixed(1)
}
</script>

<template>
  <section class="panel waypoint-list">
    <div class="panel-head">
      <h3 class="panel-title">航点列表（{{ waypointStore.count }}）</h3>
      <button class="btn btn-sm" :disabled="!waypointStore.count" @click="waypointStore.clear()">
        清空
      </button>
    </div>

    <ul class="wp-list">
      <li v-for="(p, i) in waypointStore.points" :key="i">
        <span class="wp-index">#{{ i + 1 }}</span>
        <span class="wp-coord">({{ fmt(p.x) }}, {{ fmt(p.y) }}, {{ fmt(p.z) }})</span>
        <button class="wp-del" @click="waypointStore.remove(i)">×</button>
      </li>
      <li v-if="!waypointStore.count" class="wp-empty">点击 3D 场景添加航点</li>
    </ul>
  </section>
</template>
