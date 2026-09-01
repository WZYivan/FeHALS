import { defineStore } from 'pinia'

// 航点状态：三维坐标数组（Three.js 场景为唯一渲染真源，本 store 为其响应式镜像）
export const useWaypointStore = defineStore('waypoints', {
  state: () => ({
    points: [], // [{x, y, z}]
  }),
  getters: {
    count: (s) => s.points.length,
  },
  actions: {
    add(point) {
      this.points.push({ x: point.x, y: point.y, z: point.z })
    },
    remove(index) {
      if (index >= 0 && index < this.points.length) this.points.splice(index, 1)
    },
    update(index, point) {
      if (index >= 0 && index < this.points.length) {
        this.points[index] = { x: point.x, y: point.y, z: point.z }
      }
    },
    clear() {
      this.points = []
    },
  },
})
