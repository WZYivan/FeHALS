# FeHALS

**Frontend of HELIOS++ for Airborne Laser Scanning**

基于 Web 的 3D 可视化航路规划与激光仿真系统。用户通过浏览器加载三维模型，交互式设计航点与航线，配置仿真参数，调用 HELIOS++ 引擎执行激光扫描仿真，并可视化仿真生成的点云结果。

## 架构

浏览器/服务器（B/S）架构，三层：

- **前端**：Vue 3 + Three.js，负责三维场景渲染、交互式航点编辑、参数配置与点云渲染。
- **后端**：FastAPI + Python，负责航迹/XML 配置生成、调用 HELIOS++ 引擎、解析点云结果，并通过 WebSocket 推送日志。
- **仿真引擎**：HELIOS++（`helios++`），由后端以子进程方式调用。

## 目录结构

```
FeHALS/
├── backend/            # FastAPI 后端
│   ├── app/
│   │   ├── main.py     # 应用入口
│   │   ├── config.py   # 全局配置（HELIOS++ 路径等）
│   │   ├── api/        # REST 路由 + WebSocket
│   │   ├── models/     # Pydantic schema
│   │   ├── services/   # 航迹/配置生成、HELIOS++ 调用、点云解析
│   │   └── static/     # 上传模型 / 航迹 / 配置 / 结果
│   ├── requirements.txt
│   └── run.py
├── frontend/           # Vue 3 + Three.js 前端
│   └── src/
│       ├── components/ # Scene3D / ControlPanel / WaypointList / LogConsole
│       ├── stores/     # Pinia 状态
│       ├── composables/# Three.js 场景 / 航点交互 / API 客户端
│       └── assets/
├── doc/                # 项目文档（LaTeX，Elsevier CAS）
│   ├── Manuscript.tex
│   └── Makefile        # cd doc && make
└── doc/                # 项目文档（LaTeX，Elsevier CAS）
    ├── Manuscript.tex
    └── Makefile        # cd doc && make
```

## 快速开始

### 后端

```bash
conda create -n FeHALS python=3.10 -y
conda activate FeHALS
cd backend
pip install -r requirements.txt
python run.py           # http://localhost:8000（接口文档 /docs）
```

### 前端

```bash
cd frontend
npm install
npm run dev             # http://localhost:5173（/api、/ws 代理到 8000）
```

### 项目文档

```bash
cd doc
make                    # 生成 build/Manuscript.pdf
```

## HELIOS++ 集成

后端通过环境变量配置 HELIOS++ 路径与资源目录（均有默认值）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HELIOS_PATH` | `helios++` | HELIOS++ 可执行文件 |
| `HELIOS_REPO` | `/home/azusa/file/project/3rd/helios` | HELIOS++ 源仓库根目录 |
| `HELIOS_ASSETS` | 仓库根 + `python/pyhelios` | `--assets` 搜索路径（平台/扫描器目录与示例资源） |

仿真调用形式：`helios++ <survey.xml> --assets <dir...> --output <dir> [--lasOutput] [--zipOutput]`。

仅 OBJ 格式模型可参与 HELIOS++ 仿真；GLTF/STL 支持前端三维展示。

> **关于输出格式**：本机 `helios++`（Helios v2.0.1）构建的 LAS/LAZ 输出不可用（`LASopen` 返回空指针导致崩溃），因此系统**默认使用 XYZ 输出**。如需 LAS/LAZ，请重新编译 HELIOS++ 并确保正确链接 LASlib 后，在前端「输出格式」中选择 LAS/LAZ。

> **关于平台/扫描器与航高**：UAV 与 Airborne 均使用 `copter_linearpath` 平台与 `riegl_vux-1uav` 扫描器（最小测程 3m，含 `headRotateAxis`/`beamOrigin` 定义，扫描方向正确为垂轨）。系统会把**所有航点统一抬升到设定的「飞行高度」**（恒定航高），仅用航点的水平位置（x、y）规划航线。

## 文档

系统设计详见 [doc/Manuscript.tex](doc/Manuscript.tex)。
