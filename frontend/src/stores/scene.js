import { defineStore } from 'pinia'

// 场景状态：已加载模型、点云渲染参数、交互模式、加载指示
export const useSceneStore = defineStore('scene', {
  state: () => ({
    models: [], // [{id, name, url, up, visible: true, showBbox: false, bbox: {size:[w,d,h], min, max}|null}]
    activeModelId: null,
    loading: false,
    pickMode: 'waypoint', // 'waypoint' | 'rect' （弓字形选点）
    pointOptions: {
      size: 0.05,
      colorMode: 'height', // height | intensity | fixed
      opacity: 1.0,
      fixedColor: '#ffffff',
    },
  }),
  actions: {
    addModel(m) {
      this.models.push({
        id: m.id, name: m.name, url: m.url, up: m.up || 'z',
        visible: true, showBbox: false, bbox: null,
      })
      this.activeModelId = m.id
    },
    removeModel(id) {
      this.models = this.models.filter((m) => m.id !== id)
      if (this.activeModelId === id) this.activeModelId = this.models.length > 0 ? this.models[this.models.length - 1].id : null
    },
    toggleVisible(id) {
      const m = this.models.find((m) => m.id === id); if (m) m.visible = !m.visible
    },
    toggleBbox(id) {
      const m = this.models.find((m) => m.id === id); if (m) m.showBbox = !m.showBbox
    },
    setAllBbox(show) {
      this.models.forEach((m) => { m.showBbox = show })
    },
    setModelBbox(id, bbox) {
      const m = this.models.find((m) => m.id === id); if (m) m.bbox = bbox
    },
    setLoading(v) {
      this.loading = v
    },
  },
})