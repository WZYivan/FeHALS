import { useThreeScene } from './useThreeScene'

// 航点交互门面：面向组件的高层 API。
// 底层航点渲染与交互（点击添加、拖拽、选中删除）由 useThreeScene 的场景管理器实现。
export function useWaypoints() {
  const three = useThreeScene()
  return {
    // 注册交互回调：{onAdd, onMove, onRemove}
    setCallbacks: (cb) => three.setWaypointCallbacks(cb),
    // 以航点数组重建三维表示（球体 + 连线）
    renderWaypoints: (points) => three.renderWaypoints(points),
  }
}
