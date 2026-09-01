<script setup>
import { onMounted, ref } from 'vue'
import { useHeliosAPI } from '../composables/useHeliosAPI'

const api = useHeliosAPI()
const cacheData = ref(null)
const loading = ref(false)

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

function fmtSize(bytes) {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + units[i]
}

onMounted(loadCache)
</script>

<template>
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