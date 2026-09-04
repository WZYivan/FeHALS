<script setup>
import { computed, ref, watch } from 'vue'
import { useSimulationStore } from '../stores/simulation'
import { useSceneStore } from '../stores/scene'
import { useHeliosAPI } from '../composables/useHeliosAPI'
import { getParams } from '../composables/scannerSpecs'
import { useThreeScene } from '../composables/useThreeScene'

const simStore = useSimulationStore()
const sceneStore = useSceneStore()
const api = useHeliosAPI()
const three = useThreeScene()

// 场景最高点（上次自动计算时的值），用于在面板中展示
const sceneMaxZ = ref(null)
// 安全余量（米）：建议航高 = 场景模型最高点 + 安全余量
const SAFETY_MARGIN = 20

const specs = computed(() => getParams(simStore.params.platform_type))

// 模型集合变化（增/删）时，清空基于已卸载模型计算的建议航高（展示缓存 + 航高值），
// 避免继续沿用历史模型的高程
watch(
  () => sceneStore.models.map((m) => m.id),
  () => {
    if (sceneMaxZ.value !== null) {
      // 上次「建议航高」基于旧的模型集合，随增删失效，恢复平台默认航高
      simStore.params.altitude = specs.value.platform.params.altitude.default
    }
    sceneMaxZ.value = null
  },
)

const platformParams = computed(() => specs.value.platform.params)
const scannerParams = computed(() => specs.value.scanner.params)

const altWarning = computed(() => {
  const min = specs.value.scanner.params.rangeMin.default
  // 飞行器准许最大飞行高度 = min(平台参数上限, 扫描器最大测程)
  const rangeMax = specs.value.scanner.params.rangeMax?.default
  const ceiling = rangeMax != null
    ? Math.min(specs.value.platform.params.altitude.max, rangeMax)
    : specs.value.platform.params.altitude.max
  if (simStore.params.altitude < min) {
    return `航高低于扫描器最小测程 ${min} m`
  }
  if (simStore.params.altitude > ceiling) {
    return `航高超过飞行器准许最大飞行高度 ${ceiling} m`
  }
  return ''
})

// 切换平台类型时更新参数默认值
function onPlatformChange() {
  const p = specs.value.platform
  const s = specs.value.scanner
  for (const [key, spec] of Object.entries(p.params)) {
    if (simStore.params[key] < spec.min || simStore.params[key] > spec.max) {
      simStore.params[key] = spec.default
    }
  }
  for (const [key, spec] of Object.entries(s.params)) {
    if (!spec.readonly && (simStore.params[key] < spec.min || simStore.params[key] > spec.max)) {
      simStore.params[key] = spec.default
    }
  }
}

function autoAltitude() {
  const maxZ = three.getSceneMaxZ()
  if (maxZ === null) {
    simStore.addLog('WARNING', '未加载模型，无法自动计算航高')
    return
  }
  sceneMaxZ.value = maxZ

  const spec = specs.value.platform.params.altitude
  // 飞行器准许最大飞行高度 = min(平台参数上限, 扫描器最大测程)
  const rangeMax = specs.value.scanner.params.rangeMax?.default
  const maxAllowed = rangeMax != null ? Math.min(spec.max, rangeMax) : spec.max
  let recommended = Math.ceil((maxZ + SAFETY_MARGIN) * 10) / 10
  if (recommended < spec.min) recommended = spec.min
  if (recommended > maxAllowed) {
    simStore.addLog('WARNING', `建议航高 ${recommended} m 超过飞行器准许最大飞行高度 ${maxAllowed} m，已按上限设置`)
    recommended = maxAllowed
  }
  simStore.params.altitude = recommended
  simStore.addLog(
    'INFO',
    `自动计算航高：模型最高点 ${maxZ.toFixed(2)} m + 安全余量 ${SAFETY_MARGIN} m = ${recommended} m`
  )
}

async function generateConfig() {
  try {
    const res = await api.generateConfig(simStore.params)
    simStore.configId = res.config_id
    simStore.addLog('INFO', `配置文件已生成：${res.config_id}`)
  } catch (err) {
    simStore.addLog('ERROR', '配置生成失败：' + (err.response?.data?.detail || err.message))
  }
}
</script>

<template>
  <section class="panel control-panel">
    <h3 class="panel-title">仿真参数配置</h3>

    <div class="field">
      <label>平台类型</label>
      <select v-model="simStore.params.platform_type" @change="onPlatformChange">
        <option value="UAV">UAV（无人机）</option>
        <option value="Airborne">Airborne（机载）</option>
      </select>
    </div>

    <div class="section-divider">载体参数 — {{ specs.platform.label }}</div>

    <div class="field" v-for="(spec, key) in platformParams" :key="key">
      <label>{{ spec.label }} ({{ spec.unit }})</label>
      <div class="field-input-area">
        <input
          v-model.number="simStore.params[key]"
          type="number"
          :min="spec.min"
          :max="spec.max"
          :step="spec.step"
        />
        <span class="field-range">有效范围：{{ spec.min }} ~ {{ spec.max }}</span>
      </div>
    </div>
    <div class="field">
      <label>建议航高</label>
      <div class="field-input-area">
        <button class="btn btn-sm" @click="autoAltitude">自动计算航高</button>
        <span v-if="sceneMaxZ !== null" class="field-range">
          模型最高点 {{ sceneMaxZ.toFixed(2) }} m → 建议 {{ simStore.params.altitude }} m
        </span>
        <span v-else class="field-range">基于场景模型最高点推荐安全飞行高度</span>
      </div>
    </div>

    <div v-if="altWarning" class="field-hint">{{ altWarning }}</div>

    <div class="section-divider">传感器参数 — {{ specs.scanner.label }}（{{ specs.scanner.type }}）</div>

    <div class="field" v-for="(spec, key) in scannerParams" :key="key">
      <label>{{ spec.label }} ({{ spec.unit }})</label>
      <div class="field-input-area">
        <input
          v-if="!spec.readonly"
          v-model.number="simStore.params[key]"
          type="number"
          :min="spec.min"
          :max="spec.max"
          :step="spec.step"
        />
        <input
          v-else-if="spec.default !== null"
          :value="spec.default"
          type="number"
          disabled
          class="input-readonly"
        />
        <span v-else class="field-range">无上限</span>
        <span class="field-range">
          {{ spec.readonly ? (spec.default === null ? '' : '固定值') : `有效范围：${spec.min} ~ ${spec.max}` }}
        </span>
        <span v-if="spec.note" class="field-note">{{ spec.note }}</span>
      </div>
    </div>

    <div class="field">
      <label>输出格式</label>
      <select v-model="simStore.params.output_format">
        <option value="LAS">LAS</option>
        <option value="LAZ">LAZ</option>
        <option value="XYZ">XYZ</option>
      </select>
    </div>

    <button class="btn" style="width: 100%" @click="generateConfig">生成配置</button>
  </section>
</template>