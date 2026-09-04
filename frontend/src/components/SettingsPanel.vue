<script setup>
import { onMounted, ref } from 'vue'
import { useHeliosAPI } from '../composables/useHeliosAPI'

const api = useHeliosAPI()
const cacheData = ref(null)
const envData = ref(null)
const loading = ref(false)
const envLoading = ref(false)

async function loadCache() {
  loading.value = true
  try {
    const res = await api.listCache()
    cacheData.value = res.cache
  } catch (e) {
    console.error(e)
  }
  loading.value = false
}

async function clearCache(type) {
  try {
    await api.clearCache(type)
    await loadCache()
  } catch (e) {
    console.error(e)
  }
}

async function loadEnvDiag() {
  envLoading.value = true
  try {
    envData.value = await api.diagnoseEnv()
  } catch (e) {
    console.error(e)
  }
  envLoading.value = false
}

function fmtSize(bytes) {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + units[i]
}

const statusText = { ok: '正常', warning: '警告', error: '错误' }
const statusIcon = { ok: '✓', warning: '!', error: '✗' }

onMounted(() => {
  loadEnvDiag()
  loadCache()
})
</script>

<template>
  <!-- 环境诊断 -->
  <section class="panel settings-panel">
    <div class="panel-head">
      <h3 class="panel-title">环境诊断</h3>
      <button class="btn btn-sm" :disabled="envLoading" @click="loadEnvDiag">
        {{ envLoading ? '检测中...' : '重新检测' }}
      </button>
    </div>

    <div v-if="envLoading" class="settings-loading">正在检测 FeHALS 运行环境...</div>
    <div v-else-if="!envData" class="settings-loading">无法加载环境诊断信息</div>
    <template v-else>
      <!-- 整体状态 -->
      <div class="env-overall" :class="'env-overall-' + envData.overall">
        <span class="env-status-icon">{{ statusIcon[envData.overall] }}</span>
        <span class="env-status-text">{{ statusText[envData.overall] }}</span>
        <span class="env-summary">{{ envData.summary }}</span>
      </div>

      <!-- Python 后端环境 -->
      <div class="env-section">
        <div class="env-section-title">
          Python 后端环境
          <span class="env-badge" :class="'env-badge-' + envData.python_env.status">
            {{ statusIcon[envData.python_env.status] }}
            {{ statusText[envData.python_env.status] }}
          </span>
        </div>
        <div class="env-detail-row">
          <span class="env-detail-label">Python 版本</span>
          <span class="env-detail-value">{{ envData.python_env.python_version }}</span>
        </div>

        <!-- 关键依赖 -->
        <div class="env-sub-group">
          <div class="env-sub-title">关键依赖</div>
          <div class="env-check-list">
            <div
              v-for="dep in envData.python_env.critical_deps"
              :key="dep.name"
              class="env-check-item"
            >
              <span class="env-check-icon" :class="'env-icon-' + dep.status">{{ statusIcon[dep.status] }}</span>
              <span class="env-check-path">{{ dep.name }}</span>
              <span class="env-check-desc">
                {{ dep.installed ? (dep.version || '已安装') : dep.error }}
              </span>
            </div>
          </div>
        </div>

        <!-- 可选依赖 -->
        <div class="env-sub-group">
          <div class="env-sub-title">可选依赖</div>
          <div class="env-check-list">
            <div
              v-for="dep in envData.python_env.optional_deps"
              :key="dep.name"
              class="env-check-item"
            >
              <span class="env-check-icon" :class="'env-icon-' + dep.status">{{ statusIcon[dep.status] }}</span>
              <span class="env-check-path">{{ dep.name }}</span>
              <span class="env-check-desc">
                {{ dep.installed ? (dep.version || '已安装') : '未安装（部分功能受限）' }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 静态工作目录 -->
      <div class="env-section">
        <div class="env-section-title">
          静态工作目录
          <span class="env-badge" :class="'env-badge-' + (envData.static_dirs.some(d => d.status === 'error') ? 'error' : 'ok')">
            {{ statusText[envData.static_dirs.some(d => d.status === 'error') ? 'error' : 'ok'] }}
          </span>
        </div>
        <div class="env-check-list">
          <div
            v-for="d in envData.static_dirs"
            :key="d.name"
            class="env-check-item"
          >
            <span class="env-check-icon" :class="'env-icon-' + d.status">{{ statusIcon[d.status] }}</span>
            <span class="env-check-path">{{ d.label }}</span>
            <span class="env-check-desc">{{ d.message }}</span>
          </div>
        </div>
      </div>

      <!-- HELIOS++ 可执行文件（外部引擎，附加信息） -->
      <div class="env-section">
        <div class="env-section-title">
          HELIOS++ 仿真引擎
          <span class="env-badge" :class="'env-badge-' + envData.helios_executable.status">
            {{ statusIcon[envData.helios_executable.status] }}
            {{ statusText[envData.helios_executable.status] }}
          </span>
        </div>
        <div class="env-detail-row">
          <span class="env-detail-label">配置路径</span>
          <span class="env-detail-value">{{ envData.helios_executable.path }}</span>
        </div>
        <div class="env-detail-row" v-if="envData.helios_executable.resolved_path">
          <span class="env-detail-label">实际路径</span>
          <span class="env-detail-value">{{ envData.helios_executable.resolved_path }}</span>
        </div>
        <div class="env-detail-row" v-if="envData.helios_executable.status !== 'ok'">
          <span class="env-detail-hint">{{ envData.helios_executable.message }}</span>
        </div>
        <div class="env-detail-row" v-if="envData.helios_executable.status === 'ok'">
          <span class="env-detail-hint env-text-ok">{{ envData.helios_executable.message }}</span>
        </div>
      </div>
    </template>
  </section>

  <!-- 缓存管理 -->
  <section class="panel settings-panel">
    <h3 class="panel-title">缓存管理</h3>
    <div v-if="loading" class="settings-loading">加载中...</div>
    <div v-else-if="!cacheData" class="settings-loading">无法加载缓存信息</div>
    <div v-else class="cache-list">
      <div v-for="(item, key) in cacheData" :key="key" class="cache-item">
        <span class="cache-label">{{ item.label }}</span>
        <span class="cache-info">{{ item.count }} 个文件 / {{ fmtSize(item.size) }}</span>
        <button class="btn btn-sm" @click="clearCache(key)">清理</button>
      </div>
    </div>
  </section>
</template>