"""点云覆盖度分析：将点云投影到水平面网格，计算每个网格的点数密度，
生成二维密度热力图，用于评估激光扫描的覆盖完整性与均匀性。

约定
----
- 投影到 XY 平面（水平面），Z 仅用于确定高度范围（不参与密度计算）。
- 网格按点云 XY 包围盒自适应划分，无需预知场景坐标范围。
- ``grid_size`` 控制水平分辨率（默认 50×50）。
- ``statistics`` 字段满足 ``test_coverage.py`` 的契约。
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Union

import numpy as np


PointArray = Union[np.ndarray, Sequence[Sequence[float]]]


class CoverageAnalyzer:
    """二维网格化的点云覆盖度分析器。"""

    def __init__(self, grid_size: int = 50):
        if not isinstance(grid_size, int) or grid_size <= 0:
            raise ValueError(f"grid_size 必须为正整数，实际为 {grid_size!r}")
        self.grid_size = int(grid_size)

    # ------------------------------------------------------------------ #
    # 公共 API
    # ------------------------------------------------------------------ #
    def analyze(self, points: PointArray) -> Dict:
        """分析点云的二维覆盖度，返回 ``grid``/``bounds``/``statistics``。

        Parameters
        ----------
        points:
            ``(N, 3)`` 的点坐标数组（支持 list 输入）；空数组也可接受。

        Returns
        -------
        dict
            ``grid`` 为 ``grid_size × grid_size`` 的二维 numpy.int 数组；
            ``bounds`` 为 ``[min_x, min_y, min_z, max_x, max_y, max_z]``；
            ``statistics`` 含 ``total_points`` / ``max_density`` /
            ``mean_density`` / ``coverage_percentage``。
        """
        xyz = self._coerce_points(points)
        n = xyz.shape[0]

        # 空点云：返回零矩阵，避免下游除零错误
        if n == 0:
            empty_grid = np.zeros((self.grid_size, self.grid_size), dtype=np.int64)
            return {
                "grid": empty_grid.tolist(),
                "bounds": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "statistics": {
                    "total_points": 0,
                    "max_density": 0,
                    "mean_density": 0.0,
                    "coverage_percentage": 0.0,
                    "covered_cells": 0,
                },
            }

        min_x, min_y = float(xyz[:, 0].min()), float(xyz[:, 1].min())
        max_x, max_y = float(xyz[:, 0].max()), float(xyz[:, 1].max())
        min_z, max_z = float(xyz[:, 2].min()), float(xyz[:, 2].max())

        grid, _, _ = np.histogram2d(
            xyz[:, 0],
            xyz[:, 1],
            bins=self.grid_size,
            range=[[min_x, max_x], [min_y, max_y]],
        )
        # histogram2d 返回 (H, xedges, yedges)；H 形状为 (nx, ny)，无需转置。
        grid = grid.astype(np.int64)

        total_cells = self.grid_size * self.grid_size
        covered_cells = int(np.count_nonzero(grid))
        max_density = int(grid.max())
        # 平均密度按"全部格子"统计（每格期望点数），便于评估覆盖均匀性
        mean_density = float(grid.sum() / total_cells)

        return {
            "grid": grid.tolist(),
            "bounds": [min_x, min_y, min_z, max_x, max_y, max_z],
            "statistics": {
                "total_points": int(n),
                "max_density": max_density,
                "mean_density": round(mean_density, 4),
                "coverage_percentage": round(covered_cells / total_cells * 100.0, 4),
                "covered_cells": covered_cells,
            },
        }

    # ------------------------------------------------------------------ #
    # 内部工具
    # ------------------------------------------------------------------ #
    @staticmethod
    def _coerce_points(points: PointArray) -> np.ndarray:
        """将输入规整为 ``(N, 3)`` 的 float64 数组；非法输入抛出 ValueError。"""
        arr = np.asarray(points, dtype=np.float64)
        if arr.ndim == 1 and arr.size == 0:
            return arr.reshape(0, 3)
        if arr.ndim != 2 or arr.shape[1] != 3:
            raise ValueError(
                f"points 必须为 (N, 3) 形状，实际为 {arr.shape}"
            )
        return arr