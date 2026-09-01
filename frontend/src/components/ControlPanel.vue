<script setup>
import { computed } from 'vue'
import { useSimulationStore } from '../stores/simulation'
import { useHeliosAPI } from '../composables/useHeliosAPI'
import { getParams } from '../composables/scannerSpecs'

const simStore = useSimulationStore()
const api = useHeliosAPI()

const specs = computed(() => getParams(simStore.params.platform_type))

const platformParams = computed(() => specs.value.platform.params)
const scannerParams = computed(() => specs.value.scanner.params)

const altWarning = computed(() => {
  const min = specs.value.scanner.params.rangeMin.default
  if (simStore.params.altitude < min) {
    return `航高低于扫描器最小测程 ${min} m`
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
          v-else
          :value="spec.default"
          type="number"
          disabled
          class="input-readonly"
        />
        <span class="field-range">
          {{ spec.readonly ? '固定值' : `有效范围：${spec.min} ~ ${spec.max}` }}
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