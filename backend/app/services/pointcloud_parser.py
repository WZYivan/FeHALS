"""点云解析：读取 HELIOS++ 输出的 LAS/LAZ/XYZ 文件，提取坐标与统计信息。

laspy 用于 LAS/LAZ，纯文本解析用于 XYZ。返回可供前端渲染的降采样点集。
"""
from pathlib import Path
from typing import Optional

import numpy as np

# 前端渲染点上限（超过则降采样）
MAX_RENDER_POINTS = 1_000_000


def parse(file_path: str, max_points: int = MAX_RENDER_POINTS) -> dict:
    """解析点云文件，返回 {file_path, point_count, bounds, points, intensity}。

    points 为降采样后的 [[x, y, z], ...] 列表；intensity 为对应强度（若无则 None）。
    """
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"点云文件不存在：{file_path}")

    ext = p.suffix.lower()
    if ext in (".las", ".laz"):
        return _parse_las(p, max_points)
    if ext in (".xyz", ".txt"):
        return _parse_xyz(p, max_points)
    raise ValueError(f"不支持的点云格式：{ext}")


def _parse_las(p: Path, max_points: int) -> dict:
    import laspy  # 延迟导入，避免无 laspy 时启动失败

    las = laspy.read(str(p))
    xyz = np.vstack((las.x, las.y, las.z)).transpose()
    intensity = np.asarray(las.intensity) if hasattr(las, "intensity") else None
    return _build_result(str(p), xyz, intensity, max_points)


def _parse_xyz(p: Path, max_points: int) -> dict:
    # HELIOS++ 默认 ASCII 点云输出列序（见 DirectMeasurementWriteStrategy.h）：
    #   x y z intensity echo_width returnNumber pulseReturnNumber fullwaveIndex ...
    rows = []
    inten = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            rows.append((float(parts[0]), float(parts[1]), float(parts[2])))
            if len(parts) > 3:
                inten.append(float(parts[3]))
        except ValueError:
            continue
    if not rows:
        return _build_result(str(p), np.empty((0, 3)), None, max_points)
    xyz = np.asarray(rows, dtype=np.float64)
    intensity = np.asarray(inten, dtype=np.float64) if len(inten) == len(rows) else None
    return _build_result(str(p), xyz, intensity, max_points)


def _build_result(path: str, xyz: np.ndarray, intensity: Optional[np.ndarray], max_points: int) -> dict:
    n = xyz.shape[0]
    bounds = (
        [float(xyz[:, 0].min()), float(xyz[:, 1].min()), float(xyz[:, 2].min()),
         float(xyz[:, 0].max()), float(xyz[:, 1].max()), float(xyz[:, 2].max())]
        if n else [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    )

    # 降采样
    if n > max_points:
        idx = np.linspace(0, n - 1, max_points).astype(int)
        xyz = xyz[idx]
        intensity = intensity[idx] if intensity is not None else None

    result = {
        "file_path": path,
        "point_count": n,
        "bounds": bounds,
        "points": xyz.astype(float).round(6).tolist(),
        "intensity": intensity.astype(float).round(4).tolist() if intensity is not None else None,
    }
    return result


def stats(xyz: np.ndarray) -> dict:
    """点云基础特征统计（F13 复用）。"""
    if xyz.shape[0] == 0:
        return {"count": 0}
    z = xyz[:, 2]
    return {
        "count": int(xyz.shape[0]),
        "mean_z": float(z.mean()),
        "std_z": float(z.std()),
        "min_z": float(z.min()),
        "max_z": float(z.max()),
    }
