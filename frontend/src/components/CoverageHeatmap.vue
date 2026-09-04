<script setup>
/**
 * 点云覆盖度分析组件：工具栏触发 → 模态浮层 → 选择网格大小 → 分析 → Canvas 热力图 + 统计指标。
 * 数据来源：simStore.result（来自 /api/results/{task_id}）。
 */
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useSimulationStore } from '../stores/simulation'
import { useHeliosAPI } from '../composables/useHeliosAPI'

const simStore = useSimulationStore()
const api = useHeliosAPI()

const showModal = ref(false)
const gridSize = ref(50)
const analyzing = ref(false)
const errorMsg = ref('')
const canvasRef = ref(null)

// turbo 色带：深蓝 → 青 → 绿 → 黄 → 橙 → 红（高密度更醒目）
const COLOR_STOPS = [
  [0.0, [12, 32, 64]],
  [0.15, [40, 110, 200]],
  [0.35, [50, 200, 220]],
  [0.55, [120, 230, 110]],
  [0.75, [250, 220, 60]],
  [0.9, [240, 130, 40]],
  [1.0, [200, 30, 30]],
]

const hasResult = computed(() => !!simStore.result && simStore.result.points?.length)
const pointCount = computed(() => simStore.result?.point_count || 0)

function openModal() {
  errorMsg.value = ''
  if (!hasResult.value) {
    errorMsg.value = '请先执行仿真以加载点云'
    return
  }
  showModal.value = true
  nextTick(() => renderHeatmap())
}

function closeModal() {
  showModal.value = false
}

async function runAnalysis() {
  errorMsg.value = ''
  if (!hasResult.value) {
    errorMsg.value = '当前没有可用的点云数据'
    return
  }
  analyzing.value = true
  simStore.coverageAnalyzing = true
  try {
    const res = await api.analyzeCoverage(simStore.result.points, gridSize.value)
    simStore.coverageResult = res
    simStore.addLog('INFO', `覆盖度分析完成：覆盖度 ${res.statistics.coverage_percentage.toFixed(2)}%`)
    await nextTick()
    renderHeatmap()
  } catch (err) {
    const msg = err.response?.data?.detail || err.message
    errorMsg.value = '分析失败：' + msg
    simStore.addLog('ERROR', '覆盖度分析失败：' + msg)
  } finally {
    analyzing.value = false
    simStore.coverageAnalyzing = false
  }
}

// 颜色插值
function colorFor(t) {
  const x = Math.max(0, Math.min(1, t))
  for (let i = 1; i < COLOR_STOPS.length; i++) {
    const [p1, c1] = COLOR_STOPS[i - 1]
    const [p2, c2] = COLOR_STOPS[i]
    if (x <= p2) {
      const r = (x - p1) / (p2 - p1)
      return [
        Math.round(c1[0] + (c2[0] - c1[0]) * r),
        Math.round(c1[1] + (c2[1] - c1[1]) * r),
        Math.round(c1[2] + (c2[2] - c1[2]) * r),
      ]
    }
  }
  return COLOR_STOPS[COLOR_STOPS.length - 1][1]
}

function renderHeatmap() {
  const canvas = canvasRef.value
  const result = simStore.coverageResult
  if (!canvas || !result) return

  const grid = result.grid
  const rows = grid.length
  const cols = grid[0]?.length || 0
  const max = Math.max(1, result.statistics.max_density)

  // 用设备像素比避免模糊
  const dpr = window.devicePixelRatio || 1
  const cssW = canvas.clientWidth || 320
  const cssH = canvas.clientHeight || 320
  canvas.width = cssW * dpr
  canvas.height = cssH * dpr

  const ctx = canvas.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, cssW, cssH)

  const cellW = cssW / cols
  const cellH = cssH / rows

  for (let r = 0; r < rows; r++) {
    const row = grid[r]
    for (let c = 0; c < cols; c++) {
      const v = row[c]
      if (v <= 0) {
        // 空白格：淡淡的网格底色，方便看出网格划分
        ctx.fillStyle = '#f1f5f9'
        ctx.fillRect(c * cellW, r * cellH, Math.ceil(cellW), Math.ceil(cellH))
        continue
      }
      const [R, G, B] = colorFor(v / max)
      ctx.fillStyle = `rgb(${R},${G},${B})`
      ctx.fillRect(c * cellW, r * cellH, Math.ceil(cellW), Math.ceil(cellH))
    }
  }

  // 边框
  ctx.strokeStyle = '#cbd5e1'
  ctx.lineWidth = 1
  ctx.strokeRect(0.5, 0.5, cssW - 1, cssH - 1)
}

watch(
  () => simStore.coverageResult,
  () => nextTick(renderHeatmap),
)

onMounted(() => {
  if (showModal.value) renderHeatmap()
})
</script>

<template>
  <button class="cov-btn" @click="openModal" :disabled="!hasResult">
    覆盖度分析
  </button>

  <div v-if="showModal" class="cov-modal-mask" @click.self="closeModal">
    <div class="cov-modal">
      <div class="cov-modal-head">
        <h3>点云覆盖度分析</h3>
        <button class="cov-close" @click="closeModal">×</button>
      </div>

      <div class="cov-controls">
        <div class="cov-field">
          <label>网格大小</label>
          <select v-model.number="gridSize" :disabled="analyzing">
            <option :value="20">20 × 20（粗糙）</option>
            <option :value="50">50 × 50（默认）</option>
            <option :value="80">80 × 80（精细）</option>
            <option :value="100">100 × 100（极精细）</option>
          </select>
        </div>
        <button
          class="btn btn-primary"
          @click="runAnalysis"
          :disabled="analyzing || !hasResult"
        >
          {{ analyzing ? '分析中…' : '开始分析' }}
        </button>
        <span class="cov-point-count">输入点数：{{ pointCount.toLocaleString() }}</span>
      </div>

      <div v-if="errorMsg" class="cov-error">{{ errorMsg }}</div>

      <div v-if="simStore.coverageResult" class="cov-body">
        <div class="cov-canvas-wrap">
          <canvas ref="canvasRef" class="cov-canvas"></canvas>
          <div class="cov-axis-hint">X →</div>
          <div class="cov-axis-v-hint">Y ↑</div>
        </div>

        <div class="cov-stats">
          <div class="cov-stat">
            <span class="cov-stat-label">总点数</span>
            <span class="cov-stat-value">{{ simStore.coverageResult.statistics.total_points.toLocaleString() }}</span>
          </div>
          <div class="cov-stat">
            <span class="cov-stat-label">最大密度</span>
            <span class="cov-stat-value">{{ simStore.coverageResult.statistics.max_density }}</span>
            <span class="cov-stat-unit">点/格</span>
          </div>
          <div class="cov-stat">
            <span class="cov-stat-label">平均密度</span>
            <span class="cov-stat-value">{{ simStore.coverageResult.statistics.mean_density.toFixed(2) }}</span>
            <span class="cov-stat-unit">点/格</span>
          </div>
          <div class="cov-stat cov-stat-cover">
            <span class="cov-stat-label">覆盖度</span>
            <span class="cov-stat-value">{{ simStore.coverageResult.statistics.coverage_percentage.toFixed(2) }}%</span>
            <span class="cov-stat-unit">{{ simStore.coverageResult.statistics.covered_cells }} / {{ gridSize * gridSize }} 格</span>
          </div>
          <div class="cov-stat">
            <span class="cov-stat-label">X 范围</span>
            <span class="cov-stat-value-sm">
              {{ simStore.coverageResult.bounds[0].toFixed(2) }} ~ {{ simStore.coverageResult.bounds[3].toFixed(2) }}
            </span>
          </div>
          <div class="cov-stat">
            <span class="cov-stat-label">Y 范围</span>
            <span class="cov-stat-value-sm">
              {{ simStore.coverageResult.bounds[1].toFixed(2) }} ~ {{ simStore.coverageResult.bounds[4].toFixed(2) }}
            </span>
          </div>
        </div>

        <div class="cov-legend">
          <span class="cov-legend-label">密度色阶</span>
          <div class="cov-legend-bar"></div>
          <div class="cov-legend-ticks">
            <span>0</span>
            <span>{{ Math.round(simStore.coverageResult.statistics.max_density * 0.25) }}</span>
            <span>{{ Math.round(simStore.coverageResult.statistics.max_density * 0.5) }}</span>
            <span>{{ Math.round(simStore.coverageResult.statistics.max_density * 0.75) }}</span>
            <span>{{ simStore.coverageResult.statistics.max_density }}</span>
          </div>
        </div>
      </div>

      <div v-else class="cov-empty">
        点击「开始分析」生成热力图
      </div>
    </div>
  </div>
</template>

<style scoped>
.cov-btn {
  padding: 6px 14px;
  border: 1px solid #4b5563;
  border-radius: 6px;
  background: #374151;
  color: #f3f4f6;
  font-size: 13px;
  cursor: pointer;
  margin-right: 8px;
  transition: background 0.15s;
}
.cov-btn:hover:not(:disabled) {
  background: #4b5563;
}
.cov-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.cov-modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.cov-modal {
  background: #fff;
  border-radius: 10px;
  width: 720px;
  max-width: 92vw;
  max-height: 88vh;
  overflow-y: auto;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.25);
  padding: 18px 20px 20px;
}

.cov-modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  border-bottom: 1px solid #e5e7eb;
  padding-bottom: 10px;
}

.cov-modal-head h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.cov-close {
  border: none;
  background: transparent;
  font-size: 22px;
  line-height: 1;
  color: #6b7280;
  cursor: pointer;
}
.cov-close:hover {
  color: #111827;
}

.cov-controls {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.cov-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
}

.cov-field label {
  color: #4b5563;
  font-size: 12px;
}

.cov-field select {
  padding: 5px 8px;
  border: 1px solid #d1d5db;
  border-radius: 5px;
  font-size: 13px;
}

.cov-point-count {
  margin-left: auto;
  font-size: 12px;
  color: #6b7280;
}

.cov-error {
  padding: 8px 12px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
  border-radius: 6px;
  font-size: 12px;
  margin-bottom: 10px;
}

.cov-body {
  display: grid;
  grid-template-columns: 1fr 220px;
  gap: 16px;
  margin-top: 8px;
}

.cov-canvas-wrap {
  position: relative;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  overflow: hidden;
  aspect-ratio: 1 / 1;
}

.cov-canvas {
  width: 100%;
  height: 100%;
  display: block;
  image-rendering: crisp-edges;
}

.cov-axis-hint,
.cov-axis-v-hint {
  position: absolute;
  font-size: 10px;
  color: #94a3b8;
}
.cov-axis-hint {
  right: 6px;
  bottom: 2px;
}
.cov-axis-v-hint {
  left: 2px;
  top: 6px;
}

.cov-stats {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cov-stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #f8fafc;
}

.cov-stat-cover {
  background: #eff6ff;
  border-color: #bfdbfe;
}

.cov-stat-label {
  font-size: 11px;
  color: #6b7280;
}

.cov-stat-value {
  font-size: 18px;
  font-weight: 600;
  color: #111827;
  font-family: 'Consolas', monospace;
}

.cov-stat-value-sm {
  font-size: 12px;
  color: #111827;
  font-family: 'Consolas', monospace;
}

.cov-stat-unit {
  font-size: 10px;
  color: #9ca3af;
}

.cov-legend {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  grid-column: 1 / -1;
}

.cov-legend-label {
  font-size: 11px;
  color: #6b7280;
}

.cov-legend-bar {
  height: 12px;
  border-radius: 3px;
  background: linear-gradient(
    to right,
    rgb(12, 32, 64),
    rgb(40, 110, 200),
    rgb(50, 200, 220),
    rgb(120, 230, 110),
    rgb(250, 220, 60),
    rgb(240, 130, 40),
    rgb(200, 30, 30)
  );
  border: 1px solid #e5e7eb;
}

.cov-legend-ticks {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #6b7280;
  font-family: 'Consolas', monospace;
}

.cov-empty {
  margin-top: 16px;
  text-align: center;
  color: #9ca3af;
  font-size: 13px;
  padding: 40px 0;
  border: 1px dashed #e5e7eb;
  border-radius: 6px;
}
</style>