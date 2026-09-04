#!/usr/bin/env python
"""
点云覆盖度分析单元测试
运行方式：python test_coverage.py
"""

import numpy as np
from app.services.coverage import CoverageAnalyzer

def test_basic_analysis():
    """测试基本分析功能"""
    print("🧪 测试1: 基本分析功能")
    
    # 创建测试点云：100个随机点
    points = np.random.rand(100, 3) * 10  # 在0-10范围内
    points[:, 2] = np.random.rand(100) * 5  # Z轴高度
    
    analyzer = CoverageAnalyzer(grid_size=10)
    result = analyzer.analyze(points)
    
    # 验证结果结构
    assert 'grid' in result
    assert 'bounds' in result
    assert 'statistics' in result
    assert result['statistics']['total_points'] == 100
    
    print(f"  ✅ 总点数: {result['statistics']['total_points']}")
    print(f"  ✅ 最大密度: {result['statistics']['max_density']}")
    print(f"  ✅ 覆盖度: {result['statistics']['coverage_percentage']:.2f}%")
    print("  ✅ 测试通过\n")

def test_uniform_distribution():
    """测试均匀分布的点云"""
    print("🧪 测试2: 均匀分布测试")
    
    # 创建均匀分布的点云
    x = np.linspace(0, 10, 20)
    y = np.linspace(0, 10, 20)
    xx, yy = np.meshgrid(x, y)
    points = np.column_stack([xx.ravel(), yy.ravel(), np.zeros(400)])
    
    analyzer = CoverageAnalyzer(grid_size=10)
    result = analyzer.analyze(points)
    
    # 均匀分布应该每个格子都有点
    coverage = result['statistics']['coverage_percentage']
    print(f"  ✅ 覆盖度: {coverage:.2f}%")
    
    # 应该接近100%
    assert coverage > 90, f"覆盖度应该很高，实际为{coverage}%"
    print("  ✅ 测试通过\n")

def test_empty_point_cloud():
    """测试空点云"""
    print("🧪 测试3: 空点云处理")
    
    points = np.array([]).reshape(0, 3)
    analyzer = CoverageAnalyzer(grid_size=10)
    result = analyzer.analyze(points)
    
    assert result['statistics']['total_points'] == 0
    assert result['statistics']['coverage_percentage'] == 0
    print("  ✅ 空点云处理正确\n")

def test_clustered_points():
    """测试聚集点云（一个区域密集）"""
    print("🧪 测试4: 聚集点云测试")
    
    # 在中心区域生成密集点
    points = []
    for _ in range(500):
        x = 5 + np.random.randn() * 0.5
        y = 5 + np.random.randn() * 0.5
        points.append([x, y, 0])
    points = np.array(points)
    
    analyzer = CoverageAnalyzer(grid_size=10)
    result = analyzer.analyze(points)
    
    # 应该有少数格子密度很高
    max_density = result['statistics']['max_density']
    mean_density = result['statistics']['mean_density']
    
    print(f"  ✅ 最大密度: {max_density}")
    print(f"  ✅ 平均密度: {mean_density:.2f}")
    print(f"  ✅ 最大/平均比: {max_density/mean_density:.2f}")
    
    # 最大密度应该远大于平均密度
    assert max_density > mean_density * 5, "聚集点应该产生高密度区域"
    print("  ✅ 测试通过\n")

def test_grid_size_effect():
    """测试不同网格大小的影响"""
    print("🧪 测试5: 网格大小测试")
    
    points = np.random.rand(200, 3) * 10
    
    for grid_size in [10, 20, 50]:
        analyzer = CoverageAnalyzer(grid_size=grid_size)
        result = analyzer.analyze(points)
        
        # 检查网格维度
        grid = np.array(result['grid'])
        assert grid.shape == (grid_size, grid_size)
        
        print(f"  ✅ 网格 {grid_size}x{grid_size}: 覆盖度 {result['statistics']['coverage_percentage']:.2f}%")
    
    print("  ✅ 所有网格大小测试通过\n")

def run_all_tests():
    """运行所有测试"""
    print("=" * 50)
    print("🚀 开始点云覆盖度分析单元测试")
    print("=" * 50)
    print()
    
    try:
        test_basic_analysis()
        test_uniform_distribution()
        test_empty_point_cloud()
        test_clustered_points()
        test_grid_size_effect()
        
        print("=" * 50)
        print("✅ 所有测试通过！")
        print("=" * 50)
        
    except AssertionError as e:
        print(f"❌ 测试失败: {e}")
    except Exception as e:
        print(f"❌ 发生错误: {e}")

if __name__ == "__main__":
    run_all_tests()