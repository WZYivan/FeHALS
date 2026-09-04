import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'

// 高度着色渐变（蓝→青→绿→黄→红）
// 3D 点云着色（本文件）与统计直方图（PointCloudPanel）共用
export function heightColor(t) {
  const stops = [[0,0,1],[0,1,1],[0,1,0],[1,1,0],[1,0,0]]
  const x = Math.max(0, Math.min(1, t)) * (stops.length - 1)
  const i = Math.min(Math.floor(x), stops.length - 2)
  const f = x - i
  const a = stops[i], b = stops[i + 1]
  return [a[0]+(b[0]-a[0])*f, a[1]+(b[1]-a[1])*f, a[2]+(b[2]-a[2])*f]
}

export function heightCssColor(t) {
  const [r, g, b] = heightColor(t)
  return `rgb(${Math.round(r * 255)}, ${Math.round(g * 255)}, ${Math.round(b * 255)})`
}

// 单例场景管理器：负责 Three.js 场景、模型加载、点云渲染与航点交互。
let singleton = null

export function useThreeScene() {
  if (!singleton) singleton = createThreeScene()
  return singleton
}

function createThreeScene() {
  const state = {
    container: null,
    renderer: null,
    scene: null,
    camera: null,
    controls: null,
    raycaster: null,
    pointer: new THREE.Vector2(),
    grid: null,
    groundPlane: null,
    modelsGroup: null,
    waypointGroup: null,
    waypointLine: null,
    modelRoots: {}, // id -> THREE.Object3D
    pendingRemoval: new Set(), // 加载期间被删除的模型 id（丢弃竞态的幽灵对象）
    bboxHelpers: {}, // id -> THREE.Box3Helper
    modelMeshes: [], // 参与拾取的模型 Mesh（通过 refreshModelMeshes 重建）
    waypointSpheres: [], // [{mesh, index}]
    pointCloud: null,
    pcData: null, // {points, intensity}
    selectedIndex: -1,
    animationId: null,
    // 航点交互回调（由组件注入）
    wpCallbacks: { onAdd: null, onMove: null, onRemove: null },
    // 自绘拖拽
    dragTarget: null, // {mesh, index}
    dragActive: false,
    // 矩形选点模式
    pickMode: 'waypoint',
    rectPointCallback: null,
    _downX: 0,
    _downY: 0,
  }

  const WAYPOINT_COLOR = 0xff4444
  const WAYPOINT_SELECT_COLOR = 0xffff00
  const CLICK_MOVE_SQ = 25 // 点击 vs 拖动的位移阈值（像素²）

  // ---------------------------- 初始化 ----------------------------

  function init(container) {
    state.container = container
    const w = container.clientWidth
    const h = container.clientHeight

    state.renderer = new THREE.WebGLRenderer({ antialias: true })
    state.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    state.renderer.setSize(w, h)
    container.appendChild(state.renderer.domElement)

    state.scene = new THREE.Scene()
    state.scene.background = new THREE.Color(0xe9ecef)

    state.camera = new THREE.PerspectiveCamera(60, w / h, 0.1, 100000)
    // Z-up：与 HELIOS++（及地理空间）坐标一致，z 为高程轴
    state.camera.up.set(0, 0, 1)
    state.camera.position.set(10, 10, 10)
    state.camera.lookAt(0, 0, 0)

    // 灯光
    state.scene.add(new THREE.AmbientLight(0xffffff, 0.65))
    const dir = new THREE.DirectionalLight(0xffffff, 0.85)
    dir.position.set(20, 40, 20)
    state.scene.add(dir)

    // 网格与（不可见）地面拾取平面（Z-up：地面为 z=0 的 XY 平面）
    state.grid = new THREE.GridHelper(200, 200, 0x999999, 0xd0d0d0)
    state.grid.rotation.x = Math.PI / 2 // GridHelper 默认在 XZ 平面，转到 XY 平面
    state.scene.add(state.grid)
    state.groundPlane = new THREE.Mesh(
      new THREE.PlaneGeometry(100000, 100000),
      new THREE.MeshBasicMaterial({ visible: false })
    )
    // PlaneGeometry 默认即 XY 平面（法向 +Z），无需旋转
    state.groundPlane.name = 'groundPlane'
    state.scene.add(state.groundPlane)

    state.modelsGroup = new THREE.Group()
    state.scene.add(state.modelsGroup)
    state.waypointGroup = new THREE.Group()
    state.scene.add(state.waypointGroup)

    state.waypointLine = new THREE.Line(
      new THREE.BufferGeometry(),
      new THREE.LineBasicMaterial({ color: 0xffffff })
    )
    state.waypointGroup.add(state.waypointLine)

    state.controls = new OrbitControls(state.camera, state.renderer.domElement)
    state.controls.enableDamping = true
    state.controls.dampingFactor = 0.08

    state.raycaster = new THREE.Raycaster()

    // 事件监听
    const dom = state.renderer.domElement
    dom.addEventListener('pointerdown', onPointerDown)
    dom.addEventListener('pointermove', onPointerMove)
    dom.addEventListener('pointerup', onPointerUp)
    dom.addEventListener('contextmenu', onContextMenu)
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('resize', onResize)

    animate()
  }

  function dispose() {
    if (state.animationId) cancelAnimationFrame(state.animationId)
    window.removeEventListener('resize', onResize)
    window.removeEventListener('keydown', onKeyDown)
    if (state.renderer) {
      const dom = state.renderer.domElement
      dom.removeEventListener('pointerdown', onPointerDown)
      dom.removeEventListener('pointermove', onPointerMove)
      dom.removeEventListener('pointerup', onPointerUp)
      dom.removeEventListener('contextmenu', onContextMenu)
      state.controls.dispose()
      state.renderer.dispose()
      dom.remove()
    }
  }

  function animate() {
    state.animationId = requestAnimationFrame(animate)
    state.controls.update()
    state.renderer.render(state.scene, state.camera)
  }

  function onResize() {
    if (!state.renderer || !state.container) return
    const w = state.container.clientWidth
    const h = state.container.clientHeight
    state.camera.aspect = w / h
    state.camera.updateProjectionMatrix()
    state.renderer.setSize(w, h)
  }

  // ---------------------------- 拾取 ----------------------------

  function setPointer(event) {
    const rect = state.renderer.domElement.getBoundingClientRect()
    state.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
    state.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
    state.raycaster.setFromCamera(state.pointer, state.camera)
  }

  function raycastGround(event) {
    setPointer(event)
    return state.raycaster.intersectObjects([state.groundPlane], false)
  }

  function raycastWaypoints(event) {
    setPointer(event)
    const targets = state.waypointSpheres.map((s) => s.mesh)
    return state.raycaster.intersectObjects(targets, false)
  }

  // ---------------------------- 航点交互（自绘拖拽） ----------------------------

  function onPointerDown(e) {
    state._downX = e.clientX
    state._downY = e.clientY
    state.dragActive = false
    // 检查是否命中航点
    const hits = raycastWaypoints(e)
    if (hits.length) {
      const sphere = state.waypointSpheres.find((s) => s.mesh === hits[0].object)
      if (sphere) {
        state.dragTarget = { mesh: sphere.mesh, index: sphere.index }
        state.controls.enabled = false // 锁相机
      }
    }
  }

  function onPointerMove(e) {
    if (!state.dragTarget) return
    const dx = e.clientX - state._downX
    const dy = e.clientY - state._downY
    if (dx * dx + dy * dy < CLICK_MOVE_SQ) return
    state.dragActive = true
    // 射线求交地面平面 z=0，航点贴地
    const hits = raycastGround(e)
    if (hits.length) {
      const p = hits[0].point
      state.dragTarget.mesh.position.set(p.x, p.y, 0)
      updateWaypointLine()
    }
  }

  function onPointerUp(e) {
    if (e.button !== 0) return
    if (state.dragTarget) {
      if (state.dragActive) {
        // 拖拽结束 → 推送位置
        const p = state.dragTarget.mesh.position
        if (state.wpCallbacks.onMove) {
          state.wpCallbacks.onMove(state.dragTarget.index, { x: p.x, y: p.y, z: 0 })
        }
      } else {
        // 点击（无拖拽）→ 选中
        selectWaypoint(state.dragTarget.index)
      }
      state.dragTarget = null
      state.dragActive = false
      state.controls.enabled = true
      return
    }
    // 非航点拖拽 → 判断点击 vs 旋转
    const dx = e.clientX - state._downX
    const dy = e.clientY - state._downY
    if (dx * dx + dy * dy > CLICK_MOVE_SQ) return // 旋转/平移，非点击
    handleClick(e)
  }

  function handleClick(e) {
    if (state.pickMode === 'rect' && state.rectPointCallback) {
      const hits = raycastGround(e)
      if (hits.length) {
        state.rectPointCallback({ x: hits[0].point.x, y: hits[0].point.y, z: 0 })
      }
      return
    }
    // 先检查是否命中航点 → 选中
    const wpHits = raycastWaypoints(e)
    if (wpHits.length) {
      const sphere = state.waypointSpheres.find((s) => s.mesh === wpHits[0].object)
      if (sphere) { selectWaypoint(sphere.index); return }
    }
    // 命中地面 → 新增航点（z=0 贴地）
    const gHits = raycastGround(e)
    if (gHits.length && state.wpCallbacks.onAdd) {
      const p = gHits[0].point
      state.wpCallbacks.onAdd({ x: p.x, y: p.y, z: 0 })
    }
  }

  function onContextMenu(e) {
    e.preventDefault()
    const hits = raycastWaypoints(e)
    if (!hits.length) return
    const sphere = state.waypointSpheres.find((s) => s.mesh === hits[0].object)
    if (sphere && state.wpCallbacks.onRemove) {
      state.wpCallbacks.onRemove(sphere.index)
    }
  }

  function onKeyDown(e) {
    if (e.key !== 'Delete' && e.key !== 'Backspace') return
    const tag = (e.target && e.target.tagName) || ''
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) return
    if (state.selectedIndex >= 0 && state.wpCallbacks.onRemove) {
      state.wpCallbacks.onRemove(state.selectedIndex)
    }
  }

  function selectWaypoint(index) {
    state.selectedIndex = index
    state.waypointSpheres.forEach((s) => {
      s.mesh.material.color.set(
        s.index === index ? WAYPOINT_SELECT_COLOR : WAYPOINT_COLOR
      )
    })
  }

  function setWaypointCallbacks(cb) {
    state.wpCallbacks = { ...state.wpCallbacks, ...cb }
  }

  function setPickMode(mode, onRectPoint) {
    state.pickMode = mode
    state.rectPointCallback = onRectPoint || null
  }

  function renderWaypoints(points) {
    if (state.dragTarget) return // 拖拽中不重建，避免打断交互
    clearWaypointObjects()
    const geo = new THREE.SphereGeometry(0.3, 24, 24)
    points.forEach((p, i) => {
      const mat = new THREE.MeshStandardMaterial({
        color: i === state.selectedIndex ? WAYPOINT_SELECT_COLOR : WAYPOINT_COLOR,
        roughness: 0.4,
      })
      const mesh = new THREE.Mesh(geo, mat)
      mesh.position.set(p.x, p.y, 0)
      mesh.name = 'waypoint'
      state.waypointGroup.add(mesh)
      state.waypointSpheres.push({ mesh, index: i })
    })
    if (state.selectedIndex >= points.length) state.selectedIndex = -1
    updateWaypointLine()
  }

  function clearWaypointObjects() {
    state.dragTarget = null
    state.dragActive = false
    state.waypointSpheres.forEach((s) => {
      state.waypointGroup.remove(s.mesh)
      s.mesh.geometry.dispose()
      s.mesh.material.dispose()
    })
    state.waypointSpheres = []
  }

  function updateWaypointLine() {
    const positions = []
    state.waypointSpheres.forEach((s) => {
      positions.push(s.mesh.position.x, s.mesh.position.y, s.mesh.position.z)
    })
    const geo = state.waypointLine.geometry
    geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
    geo.setDrawRange(0, positions.length / 3)
    geo.computeBoundingSphere()
  }

  // ---------------------------- 模型 ----------------------------

  function loadModel(url, name, up = 'z', id) {
    return new Promise((resolve, reject) => {
      if (id) state.pendingRemoval.delete(id) // 新一次加载前清除旧的删除标记
      const ext = (name.split('.').pop() || '').toLowerCase()
      let loader
      if (ext === 'obj') loader = new OBJLoader()
      else if (ext === 'gltf' || ext === 'glb') loader = new GLTFLoader()
      else if (ext === 'stl') loader = new STLLoader()
      else {
        reject(new Error('不支持的模型格式：' + ext))
        return
      }

      const onLoaded = (obj) => {
        let root
        if (ext === 'gltf' || ext === 'glb') root = obj.scene
        else if (ext === 'stl') {
          root = new THREE.Mesh(
            obj,
            new THREE.MeshStandardMaterial({ color: 0xcccccc, side: THREE.DoubleSide })
          )
        } else root = obj

        if (up === 'y') {
          root.rotation.x = Math.PI / 2
        }

        // 加载期间模型已被删除：丢弃结果，避免产生幽灵对象
        if (id && state.pendingRemoval.has(id)) {
          disposeObject(root)
          reject(new Error('模型已删除，加载已取消'))
          return
        }

        state.modelsGroup.add(root)
        if (id) state.modelRoots[id] = root
        refreshModelMeshes()
        fitViewTo(root)
        const box = new THREE.Box3().setFromObject(root)
        const size = box.isEmpty()
          ? [0, 0, 0]
          : [Number((box.max.x - box.min.x).toFixed(2)),
             Number((box.max.y - box.min.y).toFixed(2)),
             Number((box.max.z - box.min.z).toFixed(2))]
        resolve({ root, size })
      }
      loader.load(url, onLoaded, undefined, reject)
    })
  }

  function removeModel(id) {
    state.pendingRemoval.add(id) // 标记：若有进行中的加载，完成后丢弃该模型
    const root = state.modelRoots[id]
    if (!root) return
    state.modelsGroup.remove(root)
    disposeObject(root)
    delete state.modelRoots[id]
    // 清除 bbox + label
    ;[id, id + '_label'].forEach((k) => {
      const h = state.bboxHelpers[k]
      if (h) { state.scene.remove(h); delete state.bboxHelpers[k] }
    })
    refreshModelMeshes()
  }

  function setModelVisible(id, visible) {
    const root = state.modelRoots[id]
    if (root) root.visible = visible
  }

  function setModelBbox(id, show) {
    const root = state.modelRoots[id]
    if (!root) return
    if (show) {
      if (state.bboxHelpers[id]) return
      const box = new THREE.Box3().setFromObject(root)
      const helper = new THREE.Box3Helper(box, 0x00ff00)
      state.scene.add(helper)
      state.bboxHelpers[id] = helper

      // 创建尺寸标签 Sprite
      const size = box.getSize(new THREE.Vector3())
      const center = box.getCenter(new THREE.Vector3())
      const label = makeBboxLabel(size)
      label.position.set(center.x, center.y, center.z)
      state.scene.add(label)
      state.bboxHelpers[id + '_label'] = label
    } else {
      const helper = state.bboxHelpers[id]
      if (helper) { state.scene.remove(helper); delete state.bboxHelpers[id] }
      const label = state.bboxHelpers[id + '_label']
      if (label) { state.scene.remove(label); delete state.bboxHelpers[id + '_label'] }
    }
  }

  function makeBboxLabel(size) {
    const text = `${size.x.toFixed(1)} × ${size.y.toFixed(1)} × ${size.z.toFixed(1)}`
    const canvas = document.createElement('canvas')
    canvas.width = 256
    canvas.height = 64
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = 'rgba(0,0,0,0.6)'
    if (ctx.roundRect) ctx.roundRect(0, 0, 256, 64, 8)
    else ctx.fillRect(0, 0, 256, 64)
    ctx.fill()
    ctx.fillStyle = '#00ff00'
    ctx.font = 'bold 20px Consolas, monospace'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(text, 128, 32)
    const tex = new THREE.CanvasTexture(canvas)
    tex.needsUpdate = true
    const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false })
    const sprite = new THREE.Sprite(mat)
    sprite.scale.set(8, 2, 1)
    return sprite
  }

  function clearModels() {
    Object.keys(state.modelRoots).forEach((id) => removeModel(id))
    state.modelRoots = {}
    Object.keys(state.bboxHelpers).forEach((k) => {
      state.scene.remove(state.bboxHelpers[k])
    })
    state.bboxHelpers = {}
  }

  function refreshModelMeshes() {
    state.modelMeshes = []
    Object.values(state.modelRoots).forEach((root) => {
      root.traverse((o) => { if (o.isMesh) state.modelMeshes.push(o) })
    })
  }

  // 场景最高点（所有已加载模型的世界坐标系包围盒并集的最大 Z 值）。
  // setFromObject 会应用模型的世界变换（含 Y-up → Z-up 旋转），因此结果与 HELIOS++ 高程一致。
  function getSceneMaxZ() {
    const box = new THREE.Box3()
    const tmp = new THREE.Box3()
    Object.values(state.modelRoots).forEach((root) => {
      box.union(tmp.setFromObject(root))
    })
    return box.isEmpty() ? null : box.max.z
  }

  function disposeObject(obj) {
    obj.traverse((o) => {
      if (o.geometry) o.geometry.dispose()
      if (o.material) {
        if (Array.isArray(o.material)) o.material.forEach((m) => m.dispose())
        else o.material.dispose()
      }
    })
  }

  function fitViewTo(root) {
    const box = new THREE.Box3().setFromObject(root)
    if (box.isEmpty()) return
    const center = box.getCenter(new THREE.Vector3())
    const size = box.getSize(new THREE.Vector3())
    const maxDim = Math.max(size.x, size.y, size.z, 0.01)
    const dist = maxDim * 1.8
    state.controls.target.copy(center)
    state.camera.position.set(center.x + dist, center.y + dist, center.z + dist)
    state.camera.lookAt(center)
    state.controls.update()
  }

  // ---------------------------- 点云 ----------------------------

  function setPointCloud(points, intensity, options) {
    clearPointCloud()
    if (!points || !points.length) return
    state.pcData = { points, intensity }

    const n = points.length
    const positions = new Float32Array(n * 3)
    for (let i = 0; i < n; i++) {
      positions[i * 3] = points[i][0]
      positions[i * 3 + 1] = points[i][1]
      positions[i * 3 + 2] = points[i][2]
    }
    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3))

    const colors = computeColors(points, intensity, options)
    if (colors) geo.setAttribute('color', new THREE.BufferAttribute(colors, 3))

    const mat = new THREE.PointsMaterial({
      size: options.size,
      vertexColors: !!colors,
      color: colors ? 0xffffff : new THREE.Color(options.fixedColor || '#ffffff'),
      transparent: true,
      opacity: options.opacity,
      sizeAttenuation: true,
    })

    state.pointCloud = new THREE.Points(geo, mat)
    state.scene.add(state.pointCloud)
  }

  function updatePointCloud(options) {
    if (!state.pointCloud || !state.pcData) return
    const mat = state.pointCloud.material
    mat.size = options.size
    mat.opacity = options.opacity
    const colors = computeColors(state.pcData.points, state.pcData.intensity, options)
    if (colors) {
      state.pointCloud.geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))
      mat.vertexColors = true
      mat.color.set(0xffffff)
    } else {
      state.pointCloud.geometry.deleteAttribute('color')
      mat.vertexColors = false
      mat.color.set(options.fixedColor || '#ffffff')
    }
    mat.needsUpdate = true
  }

  function clearPointCloud() {
    if (state.pointCloud) {
      state.scene.remove(state.pointCloud)
      state.pointCloud.geometry.dispose()
      state.pointCloud.material.dispose()
      state.pointCloud = null
      state.pcData = null
    }
  }

  function computeColors(points, intensity, options) {
    if (options.colorMode === 'height') return heightColors(points)
    if (options.colorMode === 'intensity' && intensity && intensity.length) {
      return intensityColors(intensity)
    }
    return null
  }

  function heightColors(points) {
    let min = Infinity, max = -Infinity
    for (const p of points) { if (p[2] < min) min = p[2]; if (p[2] > max) max = p[2] }
    const span = max - min || 1
    const colors = new Float32Array(points.length * 3)
    for (let i = 0; i < points.length; i++) {
      const c = heightColor((points[i][2] - min) / span)
      colors[i * 3] = c[0]; colors[i * 3 + 1] = c[1]; colors[i * 3 + 2] = c[2]
    }
    return colors
  }

  function intensityColors(intensity) {
    let min = Infinity, max = -Infinity
    for (const v of intensity) { if (v < min) min = v; if (v > max) max = v }
    const span = max - min || 1
    const colors = new Float32Array(intensity.length * 3)
    for (let i = 0; i < intensity.length; i++) {
      const c = heightColor((intensity[i] - min) / span)
      colors[i * 3] = c[0]; colors[i * 3 + 1] = c[1]; colors[i * 3 + 2] = c[2]
    }
    return colors
  }

  return {
    init, dispose,
    loadModel, removeModel, clearModels,
    setModelVisible, setModelBbox,
    setPointCloud, updatePointCloud, clearPointCloud,
    setWaypointCallbacks, renderWaypoints,
    setPickMode,
    getSceneMaxZ,
    get scene() { return state.scene },
    get camera() { return state.camera },
  }
}