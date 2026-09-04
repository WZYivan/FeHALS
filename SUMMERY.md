# FeHALS 开发日志

## 2026-09-01

最初规划了基于 QGIS API 的桌面应用路线，计划利用 QGIS 的三维可视化能力与 C++ 插件接口构建 FeHALS。但在调研后发现，HELIOS++ 官方已有一个名为 AEOS 的 QGIS Plugin，实现了类似的功能。此外，在 WSL 环境下 QGIS 的 GUI 组件难以正常渲染，且 QGIS 插件的开发与部署流程较为复杂，不利于快速迭代和跨平台分发。综合考虑后，决定抛弃 QGIS 路线，转向浏览器/服务器（B/S）架构。

转向 Web 架构后，完成了整个 FeHALS 系统的搭建。后端基于 FastAPI 和 Python 3.10（conda 环境 FeHALS）实现了 REST API（模型上传/列表/删除、航迹生成/下载、配置生成、仿真执行/状态/日志/取消、结果解析/下载）以及 WebSocket 日志实时推送。仿真引擎通过 asyncio 子进程调用 helios++ 可执行文件，点云结果利用 laspy 解析 LAS/LAZ 或文本方式解析 XYZ 格式，支持百万点降采样和强度提取。

前端基于 Vue 3、Vite 和 Three.js 构建，搭配 Pinia 状态管理，实现了三维场景渲染（Z-up 坐标系，与 HELIOS++ 一致）、模型加载（OBJ/GLTF/STL，含 Y-up 自动旋转）、交互式航点编辑（自绘拖拽锁相机、贴地 z=0）、弓字形自动航迹、恒定高航迹导出、仿真参数图形化配置（含参数规格库与范围校验）、HELIOS++ 引擎调用与日志实时推送、点云渲染与导出、模型列表管理（可见性/bbox/移除）、缓存清理等核心功能。侧边栏采用 5 个 Tab 布局（仿真参数、点云、模型列表、航迹、设置），底部有日志控制台。

文档方面，重写了 `doc/Manuscript.tex`，将标题/摘要/亮点/关键词从 QGIS 插件描述改为 Web 架构描述，补全了所有章节，新增了 AEOS 对比与架构取舍说明，更新了参考文献。

在集成过程中修复了多个问题：HELIOS++ 轨迹解析对数据行中的空格敏感、本机 helios++ 构建的 LAS 输出不可用、扫描器 ID 错误、前端 UI 被场景画布遮挡、Y/Z 轴约定不一致、模型 up 轴检测、扫描方向为沿轨而非垂轨等。创建了 `run.sh` 脚本支持一键启动/停止前后端，以及 `CHANGELOG.md` 和 `SUMMERY.md` 记录项目变更。

## 2026-09-02

将本地仓库上传至github云端repo [FeHALS](https://github.com/WZYivan/FeHALS)，同时编写了 [CODEOWENRS](.github/CODEOWENRS) 和 `branch rules` 以规范代码贡献流程。在此基础上，梅康凯与唐如意分别提交了两个PR：自动航高计算+Windows平台启动脚本 `run.bat` 、点云特征统计。我指导它们二人熟悉 `git` 以及 [github](www.github.com) 的基本功能与使用。这两个PR尚在review阶段，我还没有merge。

文档方面，我为 [Elsevier CAS Bundle](doc/Manuscript.tex) 添加了 [南京林业大学风格的封面](doc/njfutitlepage.sty) ，修正了一些引用方面的位置错误。并预计为文档添加合适的 `Graphic Abstract` 、图片等内容以丰富文档内容。

除了梅康凯与唐如意二人，尚未有其他人询问代码贡献事宜，即使我已经在合作群中发布公告。

## 2026-09-03

在`2026-09-01`的基本开发完成之后，后续功能的开发工作已整理成列表在 [TODO](TODO.md) 中以指导各个成员选择合适的路径开发与贡献代码，本人将此后的精力集中于文档、图表的整理和项目的管理统筹。

文档方面，主要是 [说明文档](doc/Manuscript.tex)，包含了相关技术、需求分析、系统架构、设计实现、未来展望等内容。这些暂时都是由我负责。目前仅仅填充了内容但还尚未优化，整体较为粗糙，也严重缺乏图、表等直观的说明性内容。这些都有待进一步优化。

项目管理方面，统一使用 `git` 进行版本控制、 [github](www.github.com) 进行合作开发。以我的repo [FeHALS](https://github.com/WZYivan/FeHALS) 为父仓库，所有组员通过 `fork` 复制一份独立的repo进行开发，然后通过 `pull request` 操作请求审阅。在我（`CODEOWNER`）审阅之后即可 `merge` 到主分支。这样所有的操作历史、作者、来源清晰可查，组员的开发也不会互相干扰。同时，这还保持了主分支的纯洁与安全性，保证只有审阅过的安全、有效的代码才会进入仓库。

今日合并了多个PR，分别来自梅康凯、唐如意和杨杰瑞三人：
- 梅康凯：添加了自动航高计算、Windows系统启动脚本、修复了模型列表的相关的一些BUG。
- 唐如意：添加了实时点云信息统计、增强了系统解析大点云文件的性能。
- 杨杰瑞：绘制了 [系统架构图](doc/figs/src/detialed_fehals_arch.drawio) 、[数据流向图](doc/figs/src/detialed_fehals_workflow.drawio)、 [图概](doc/figs/src/graphicalabstract.drawio)。

> 本人的开发环境是 `WSL` ，属于Linux系统，因此最初没有Windows系统的适配。