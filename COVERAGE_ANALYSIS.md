# 点云覆盖度分析功能文档

## 概述

点云覆盖度分析功能将点云投影到水平网格，计算每个网格单元的点密度，并生成热力图和等高线图可视化。

## 功能特性

- **网格投影**: 将 3D 点云投影到 2D 水平网格
- **密度计算**: 统计每个网格单元内的点数
- **统计分析**: 计算覆盖率、平均密度、最大/最小密度等指标
- **可视化生成**: 自动生成热力图和等高线图
- **多格式支持**: 支持 LAS/LAZ/XYZ 点云格式

## API 端点

### 1. POST /api/analysis/coverage

执行点云覆盖度分析。

**请求体 (JSON):**

```json
{
  "task_id": "sim_1234567890_abc123",  // 可选：分析已完成的仿真结果
  "file_path": "/path/to/pointcloud.xyz",  // 可选：或直接指定点云文件
  "grid_size": 1.0,  // 网格单元大小（米），默认 1.0
  "generate_heatmap": true,  // 是否生成热力图，默认 true
  "generate_contour": true,  // 是否生成等高线图，默认 true
  "heatmap_cmap": "hot",  // 热力图色图，默认 "hot"
  "contour_levels": 10  // 等高线层数，默认 10
}
```

**注意**: `task_id` 和 `file_path` 必须提供其中之一。

**可用色图**:
- `hot`: 黑-红-黄-白（经典热力图）
- `viridis`: 紫-蓝-绿-黄（感知均匀）
- `plasma`: 紫-红-黄（高对比度）
- `jet`: 蓝-青-绿-黄-红（彩虹色）
- `coolwarm`: 蓝-白-红（冷暖对比）
- `inferno`: 黑-紫-红-黄（火焰色）

**响应示例:**

```json
{
  "file_path": "/path/to/pointcloud.xyz",
  "grid_size": 1.0,
  "coverage": {
    "grid_size": 1.0,
    "bounds": [0.0, 0.0, 100.0, 100.0],  // [xmin, ymin, xmax, ymax]
    "grid_shape": [100, 100],  // [rows, cols]
    "density_grid": [[0, 5, 10, ...], ...],  // 密度网格（每单元点数）
    "stats": {
      "total_points": 50000,
      "covered_cells": 8523,
      "total_cells": 10000,
      "coverage_ratio": 0.8523,  // 覆盖率 85.23%
      "mean_density": 5.87,  // 平均密度（仅统计有点单元）
      "max_density": 45,
      "min_density": 1
    }
  },
  "heatmap_url": "/static/results/sim_xxx/pointcloud_heatmap.png",
  "contour_url": "/static/results/sim_xxx/pointcloud_contour.png"
}
```

### 2. GET /api/analysis/coverage/{task_id}

获取指定仿真任务的覆盖度分析（快捷方式）。

**查询参数:**
- `grid_size`: 网格大小（米），默认 1.0
- `generate_viz`: 是否生成可视化，默认 true

**示例:**
```
GET /api/analysis/coverage/sim_1234567890_abc123?grid_size=2.0&generate_viz=true
```

## Python API 使用

### 方式 1: 从文件分析

```python
from app.services import coverage_analysis

# 分析点云文件并生成可视化
result = coverage_analysis.analyze_coverage_from_file(
    file_path="output/pointcloud.xyz",
    grid_size=1.0,  # 1m 网格
    generate_viz=True,
    output_dir="output",  # 可选，默认与点云同目录
    heatmap_cmap="hot",
    contour_levels=10,
)

# 访问结果
print(f"总点数: {result['coverage']['stats']['total_points']}")
print(f"覆盖率: {result['coverage']['stats']['coverage_ratio']:.2%}")
print(f"热力图: {result['heatmap_path']}")
print(f"等高线图: {result['contour_path']}")
```

### 方式 2: 从点云数组分析

```python
import numpy as np
from app.services import coverage_analysis

# 加载点云数据
xyz = np.loadtxt("pointcloud.xyz", usecols=(0, 1, 2))

# 分析覆盖度
result = coverage_analysis.analyze_coverage(
    xyz=xyz,
    grid_size=2.0,  # 2m 网格
    bounds=None,  # None 则自动计算边界
)

# 访问统计信息
stats = result["stats"]
print(f"覆盖单元数: {stats['covered_cells']}")
print(f"总单元数: {stats['total_cells']}")
print(f"覆盖率: {stats['coverage_ratio']:.2%}")

# 生成热力图
import numpy as np
density_grid = np.array(result["density_grid"])
coverage_analysis.generate_heatmap(
    density_grid=density_grid,
    output_path="heatmap.png",
    bounds=tuple(result["bounds"]),
    grid_size=result["grid_size"],
    cmap="viridis",
)
```

## 命令行测试

运行测试脚本：

```bash
cd backend
python test_coverage_analysis.py
```

测试脚本会：
1. 创建示例点云（模拟多条扫描带）
2. 执行覆盖度分析
3. 生成热力图和等高线图
4. 显示统计结果

## 结果解读

### 统计指标

- **total_points**: 点云总点数
- **covered_cells**: 包含至少 1 个点的网格单元数
- **total_cells**: 网格总单元数
- **coverage_ratio**: 覆盖率 = covered_cells / total_cells
- **mean_density**: 平均点密度（仅统计有点的单元）
- **max_density**: 单个单元的最大点数
- **min_density**: 单个单元的最小点数（仅统计有点的单元）

### 热力图解读

- **颜色**: 从冷色（低密度）到暖色（高密度）
- **白色/黑色区域**: 无点覆盖的区域
- **高亮区域**: 点密度集中的区域（可能是重叠扫描带）

### 等高线图解读

- **等高线**: 连接相同密度值的线
- **密集区域**: 等高线密集表示密度变化剧烈
- **标注数值**: 每条等高线的密度值

## 应用场景

### 1. 扫描质量评估

```python
# 分析仿真结果的覆盖质量
result = coverage_analysis.analyze_coverage_from_file(
    "simulation_result.xyz",
    grid_size=0.5,  # 精细网格
)

# 检查覆盖率是否达标
if result['coverage']['stats']['coverage_ratio'] < 0.9:
    print("警告: 覆盖率不足 90%")
```

### 2. 航线优化

比较不同航线规划的覆盖效果：

```python
results = []
for trajectory in ["traj_1.trj", "traj_2.trj", "traj_3.trj"]:
    # 运行仿真...
    result = coverage_analysis.analyze_coverage_from_file(
        result_file,
        grid_size=1.0,
    )
    results.append({
        "trajectory": trajectory,
        "coverage": result['coverage']['stats']['coverage_ratio'],
        "mean_density": result['coverage']['stats']['mean_density'],
    })

# 选择最佳航线
best = max(results, key=lambda x: x['coverage'])
print(f"最佳航线: {best['trajectory']}, 覆盖率: {best['coverage']:.2%}")
```

### 3. 不同网格分辨率对比

```python
for grid_size in [0.5, 1.0, 2.0, 5.0]:
    result = coverage_analysis.analyze_coverage_from_file(
        "pointcloud.xyz",
        grid_size=grid_size,
        generate_viz=True,
    )
    print(f"网格 {grid_size}m: 覆盖率 {result['coverage']['stats']['coverage_ratio']:.2%}")
```

## 性能考虑

- **网格大小**: 较小的网格提供更精细的分析，但计算量更大
- **点云规模**: 百万级点云分析通常在秒级完成
- **内存使用**: 网格维度限制为 10000×10000，避免内存溢出
- **建议网格大小**:
  - UAV 扫描 (低空): 0.5-1.0 m
  - 机载扫描 (高空): 1.0-5.0 m
  - 快速评估: 5.0-10.0 m

## 故障排除

### 错误: "网格维度过大"

**原因**: 点云范围太大，或网格大小设置过小。

**解决**:
```python
# 增大网格大小
result = coverage_analysis.analyze_coverage_from_file(
    file_path,
    grid_size=5.0,  # 从 1.0 增加到 5.0
)

# 或裁剪区域
bounds = (xmin, ymin, xmax, ymax)  # 指定感兴趣区域
result = coverage_analysis.analyze_coverage(xyz, bounds=bounds)
```

### 错误: "点云文件不存在"

**检查**:
- 文件路径是否正确
- 仿真任务是否已完成
- 使用绝对路径或相对于后端目录的路径

### 可视化图片无法显示

**检查**:
- 图片文件是否生成在正确的目录
- 静态文件服务是否正确配置
- 浏览器是否能访问 `/static/results/` 路径

## 扩展开发

### 自定义色图

```python
from matplotlib.colors import LinearSegmentedColormap

# 创建自定义色图
colors = ['blue', 'cyan', 'yellow', 'red']
n_bins = 100
cmap = LinearSegmentedColormap.from_list('custom', colors, N=n_bins)

coverage_analysis.generate_heatmap(
    density_grid, output_path, bounds, grid_size,
    cmap=cmap,  # 使用自定义色图
)
```

### 添加新的分析指标

在 `coverage_analysis.py` 的 `analyze_coverage` 函数中添加：

```python
# 计算密度标准差
std_density = float(covered_densities.std()) if covered_cells > 0 else 0.0

# 计算密度分位数
p25 = float(np.percentile(covered_densities, 25)) if covered_cells > 0 else 0
p75 = float(np.percentile(covered_densities, 75)) if covered_cells > 0 else 0

# 添加到统计结果
stats["std_density"] = std_density
stats["p25_density"] = p25
stats["p75_density"] = p75
```

## 参考资料

- Matplotlib 色图参考: https://matplotlib.org/stable/tutorials/colors/colormaps.html
- NumPy 数组操作: https://numpy.org/doc/stable/reference/routines.array-manipulation.html
- FastAPI 文档: https://fastapi.tiangolo.com/
