<script setup>
import { computed } from 'vue'
import { useSceneStore } from '../stores/scene'
import { useSimulationStore } from '../stores/simulation'
import { heightCssColor } from '../composables/useThreeScene'

const sceneStore = useSceneStore()
const simStore = useSimulationStore()

// 特征统计（旧响应可能无 stats 字段，空点云时仅有 count）
const st = computed(() => simStore.result?.stats || {})
const hist = computed(() => st.value.z_histogram || null)
const maxBin = computed(() => (hist.value ? Math.max(...hist.value.bins, 1) : 1))

const HIST_W = 300
const HIST_H = 70

function binColor(i) {
  const n = hist.value.bins.length
  return heightCssColor(n <= 1 ? 0 : i / (n - 1))
}

function binTip(i) {
  const h = hist.value
  const start = h.min + h.bin_size * i
  return `${start.toFixed(2)} ~ ${(start + h.bin_size).toFixed(2)} m：${h.bins[i]} 点`
}

const fmt = (v, d = 2) => (v == null || Number.isNaN(Number(v)) ? '—' : Number(v).toFixed(d))
const fmtInt = (v) => (v == null ? '—' : Number(v).toLocaleString('en-US'))
const fmtRange = (a, b) => `${fmt(a)} ~ ${fmt(b)}`

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
    <h3 class="panel-title">点云</h3>

    <div v-if="!simStore.result" class="pc-empty">暂无点云数据，请先执行仿真</div>

    <template v-if="simStore.result">
      <div class="section-divider">特征统计</div>
      <div class="stat-list">
        <div class="stat-item">
          <span class="stat-label">点数</span>
          <span class="stat-value">{{ fmtInt(simStore.result.point_count) }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">X 范围</span>
          <span class="stat-value">{{ fmtRange(simStore.result.bounds?.[0], simStore.result.bounds?.[3]) }} m</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Y 范围</span>
          <span class="stat-value">{{ fmtRange(simStore.result.bounds?.[1], simStore.result.bounds?.[4]) }} m</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Z 范围</span>
          <span class="stat-value">{{ fmtRange(simStore.result.bounds?.[2], simStore.result.bounds?.[5]) }} m</span>
        </div>
      </div>

      <div class="field" v-if="hist">
        <label>高度分布</label>
        <svg class="hist-svg" :viewBox="`0 0 ${HIST_W} ${HIST_H}`" preserveAspectRatio="none">
          <rect
            v-for="(c, i) in hist.bins"
            :key="i"
            :x="(i / hist.bins.length) * HIST_W"
            :y="HIST_H - (c / maxBin) * HIST_H"
            :width="(HIST_W / hist.bins.length) * 0.85"
            :height="(c / maxBin) * HIST_H"
            :fill="binColor(i)"
          >
            <title>{{ binTip(i) }}</title>
          </rect>
        </svg>
        <div class="hist-labels">
          <span>{{ fmt(hist.min) }}</span>
          <span>m</span>
          <span>{{ fmt(hist.max) }}</span>
        </div>
      </div>

      <div class="section-divider">高度</div>
      <div class="stat-list">
        <div class="stat-item">
          <span class="stat-label">平均高度</span>
          <span class="stat-value">{{ fmt(st.mean_z) }} m</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">高度标准差</span>
          <span class="stat-value">{{ fmt(st.std_z) }} m</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">高度中位数</span>
          <span class="stat-value">{{ fmt(st.median_z) }} m</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">P5 ~ P95</span>
          <span class="stat-value">{{ fmtRange(st.p05_z, st.p95_z) }} m</span>
        </div>
      </div>

      <template v-if="st.intensity">
        <div class="section-divider">强度</div>
        <div class="stat-list">
          <div class="stat-item">
            <span class="stat-label">强度均值</span>
            <span class="stat-value">{{ fmt(st.intensity.mean) }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">强度范围</span>
            <span class="stat-value">{{ fmtRange(st.intensity.min, st.intensity.max) }}</span>
          </div>
        </div>
      </template>

      <div class="section-divider">渲染属性</div>

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
