// 弓字形航迹生成：给定矩形两角点与行间距，返回航点数组
export function generateBowtie(p1, p2, spacing) {
  const minX = Math.min(p1.x, p2.x)
  const maxX = Math.max(p1.x, p2.x)
  const minY = Math.min(p1.y, p2.y)
  const maxY = Math.max(p1.y, p2.y)

  const points = []
  const ys = []
  for (let y = minY; y <= maxY + 1e-6; y += spacing) ys.push(y)
  if (ys.length === 0 || ys[ys.length - 1] < maxY - 1e-6) ys.push(maxY)

  ys.forEach((y, i) => {
    if (i % 2 === 0) {
      points.push({ x: minX, y, z: 0 })
      points.push({ x: maxX, y, z: 0 })
    } else {
      points.push({ x: maxX, y, z: 0 })
      points.push({ x: minX, y, z: 0 })
    }
  })
  return points
}