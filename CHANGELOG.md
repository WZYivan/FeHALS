# Changelog

## Unreleased

### Added
- 航高自动计算：基于场景模型最高点 + 安全余量（20 m）推荐安全飞行高度（ControlPanel「建议航高」按钮 + useThreeScene.getSceneMaxZ）

## v0.1.0 (2026-09-02)

### Added
- 参数规格库（scannerSpecs.js）：扫描器/平台参数有效范围、默认值、步长
- 仿真参数 Tab 分为「载体参数」与「传感器参数」两个模块，显示各参数有效范围
- 执行仿真前参数校验，超出范围拒绝执行并提示
- 平台切换自动重置参数至默认值
- 扫描器/平台只读参数显示（光束发散角、最小测程）
- 场景中模型 bbox 显示尺寸精灵
- 设置 Tab（缓存统计 + 清理）
- 航迹管理 Tab（航迹列表 + 弓字形面板）
- SUMMERY.md 中文开发日志
- CHANGELOG.md 变更记录

### Changed
- 扫描器选型：Airborne → `copter_linearpath` + `riegl_vux-1uav`（含 beamOrigin/headRotateAxis，扫描方向正确为垂轨）
- 移除 survey XML 的 `rotationSpec="CANONICAL"` 与 scannerMount 覆盖，使用平台默认安装
- 侧边栏 Tab：「点云渲染」→「点云」，点云下载整合至 Tab 内
- 模型列表删除 bbox 全选按钮
- 仿真参数输入改为纵向布局（标签在上、输入框居中、有效范围在输入框下方）

### Fixed
- 模型删除后列表仍显示（loadedIds 未同步移除）
- 扫描方向为沿轨而非垂轨（改用 copter_linearpath + riegl_vux-1uav）

### Removed
- `helios-demo/` 目录

## v0.1.0 (2026-09-01)

### Added
- 3D 场景渲染（Three.js，Z-up 坐标系，网格地面，OrbitControls）
- 模型上传与加载（OBJ/GLTF/STL，自动适配视图，Y-up 自动旋转）
- 交互式航点编辑（鼠标点击添加、航点贴地 z=0、自绘拖拽锁相机、Delete/右键删除）
- 白色折线连接航点形成航线
- 航迹导出（HELIOS++ 原生 .trj CSV，恒定飞行高度）
- 仿真参数配置面板（平台类型/飞行速度/航高/扫描频率/角度/脉冲频率/输出格式）
- 弓字形自动航迹生成（矩形区域点两点生成，间距可配）
- HELIOS++ 仿真集成（asyncio 子进程调用，实时日志捕获，进度百分比，WebSocket 推送）
- 点云渲染（Points 着色：按高度/强度/固定颜色，尺寸与透明度滑块）
- 仿真取消（后端 cancel + 前端取消按钮）
- 点云下载（仿真完成后下载 LAS/LAZ/XYZ）
- 日志控制台（分级日志 INFO/WARNING/ERROR，自动滚动，清空）
- 可拖拽布局（侧边栏宽度/控制台高度手柄）
- 模型列表 Tab（可见性切换、移除、bbox 线框 + 尺寸文本）
- 点云渲染 Tab（尺寸/透明度/着色/颜色，移出场景浮层）
- 航迹管理 Tab（航点列表 + 弓字形面板）
- 设置 Tab（缓存目录大小统计 + 清理）
- 航高校验（UAV 最小测程 3m，Airborne 最小测程 100m，不足时警告 + 拒绝执行）
- 模型 up 轴自动检测（Y-up 模型在 Three.js 与 HELIOS++ 中一致旋转到 Z-up）
- 项目文档（doc/Manuscript.tex，Elsevier CAS 模板，中文）

### Changed
- 扫描器选型：Airborne 使用 `leica_als50-ii`（具 `rotationSpec="CANONICAL"` + scannerMount，扫描方向正确为垂轨）
- 侧边栏改为多 Tab 布局（5 个：仿真参数 / 点云渲染 / 模型列表 / 航迹 / 设置）
- Three.js 场景从 Y-up 改为 Z-up（与 HELIOS++ 坐标一致）
- 移除 DragControls，改为自绘拖拽（锁相机 + 航点贴地）
- 点云渲染控件从场景浮层移入侧边栏 Tab
- 移除 Terrestrial/TLS 平台选项
- 移除 `helios-demo/` 目录

### Fixed
- 仿真进度百分比恒为 0（正则无法匹配小数点格式 `50.00%`）
- 航点拖拽时相机视角跟随转动（自绘拖拽锁定相机）
- 航点高程未按恒定飞行高度（所有航点统一为 altitude）
- 模型 Y/Z 轴指向不一致（Three.js 与 HELIOS++ 的 up 轴旋转对齐）
- 扫描方向为沿轨而非垂轨（改用 `leica_als50-ii` + scannerMount）

### Known Issues
- LAS/LAZ 输出不可用：本机 helios++ 构建的 LAS 输出崩溃（`LASwriter` 空指针），默认使用 XYZ 输出
- Airborne 扫描器最小测程 100m，低空扫描请使用 UAV 平台