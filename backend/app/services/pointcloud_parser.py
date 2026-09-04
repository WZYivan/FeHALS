"""点云解析：读取 HELIOS++ 输出的 LAS/LAZ/XYZ 文件，提取坐标与统计信息。

laspy 用于 LAS/LAZ，纯文本解析用于 XYZ。返回可供前端渲染的降采样点集。
"""
from pathlib import Path
from typing import Optional

import numpy as np

# 前端渲染点上限（超过则降采样）
MAX_RENDER_POINTS = 1_000_000

# 高度分布直方图分箱数
HISTOGRAM_BINS = 40


def parse(file_path: str, max_points: int = MAX_RENDER_POINTS) -> dict:
    """解析点云文件，返回 {file_path, point_count, bounds, stats, points, intensity}。

    points 为降采样后的 [[x, y, z], ...] 列表；intensity 为对应强度（若无则 None）；
    stats 为全量点的特征统计（高度统计、强度统计、高度分布直方图，不受降采样影响）。
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
    # 逐行流式读取；分块转为 ndarray，避免千万级行的 Python 列表整体驻留内存
    _CHUNK_ROWS = 500_000
    blocks: list = []
    inten_blocks: list = []
    buf: list = []
    ibuf: list = []
    has_inten = True  # 任一有效行缺第 4 列即整体丢弃强度（与旧实现语义一致）
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 3:
                continue
            try:
                buf.append((float(parts[0]), float(parts[1]), float(parts[2])))
                if len(parts) > 3 and has_inten:
                    ibuf.append(float(parts[3]))
                else:
                    has_inten = False
            except ValueError:
                continue
            if len(buf) >= _CHUNK_ROWS:
                blocks.append(np.asarray(buf, dtype=np.float64))
                inten_blocks.append(np.asarray(ibuf, dtype=np.float64))
                buf, ibuf = [], []
    if buf:
        blocks.append(np.asarray(buf, dtype=np.float64))
        inten_blocks.append(np.asarray(ibuf, dtype=np.float64))
    if not blocks:
        return _build_result(str(p), np.empty((0, 3)), None, max_points)
    xyz = blocks[0] if len(blocks) == 1 else np.vstack(blocks)
    intensity = np.concatenate(inten_blocks) if has_inten and len(inten_blocks) else None
    return _build_result(str(p), xyz, intensity, max_points)


def _build_result(path: str, xyz: np.ndarray, intensity: Optional[np.ndarray], max_points: int) -> dict:
    n = xyz.shape[0]
    bounds = (
        [float(xyz[:, 0].min()), float(xyz[:, 1].min()), float(xyz[:, 2].min()),
         float(xyz[:, 0].max()), float(xyz[:, 1].max()), float(xyz[:, 2].max())]
        if n else [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    )
    # 特征统计基于全量点（降采样仅影响渲染点集）
    point_stats = stats(xyz, intensity)

    # 降采样
    if n > max_points:
        idx = np.linspace(0, n - 1, max_points).astype(int)
        xyz = xyz[idx]
        intensity = intensity[idx] if intensity is not None else None

    result = {
        "file_path": path,
        "point_count": n,
        "bounds": bounds,
        "stats": point_stats,
        "points": xyz.astype(float).round(6).tolist(),
        "intensity": intensity.astype(float).round(4).tolist() if intensity is not None else None,
    }
    return result


def stats(xyz: np.ndarray, intensity: Optional[np.ndarray] = None) -> dict:
    """点云特征统计：点数、高度统计（均值/标准差/中位数/P5/P95/范围）、
    强度统计（有强度数据时）与高度分布直方图。均基于传入的全量点集。
    """
    n = xyz.shape[0]
    if n == 0:
        return {"count": 0}
    z = xyz[:, 2]
    result = {
        "count": int(n),
        "mean_z": float(z.mean()),
        "std_z": float(z.std()),
        "min_z": float(z.min()),
        "max_z": float(z.max()),
        "median_z": float(np.percentile(z, 50)),
        "p05_z": float(np.percentile(z, 5)),
        "p95_z": float(np.percentile(z, 95)),
        "z_histogram": _z_histogram(z),
    }
    if intensity is not None and intensity.shape[0] == n:
        result["intensity"] = {
            "mean": float(intensity.mean()),
            "std": float(intensity.std()),
            "min": float(intensity.min()),
            "max": float(intensity.max()),
        }
    return result


def _z_histogram(z: np.ndarray, bins: int = HISTOGRAM_BINS) -> dict:
    """高度分布直方图（等宽分箱），供前端渲染分布图。"""
    z_min, z_max = float(z.min()), float(z.max())
    if z_min == z_max:
        return {"min": z_min, "max": z_max, "bin_size": 0.0, "bins": [int(z.shape[0])]}
    counts, _ = np.histogram(z, bins=bins, range=(z_min, z_max))
    return {
        "min": z_min,
        "max": z_max,
        "bin_size": (z_max - z_min) / bins,
        "bins": counts.astype(int).tolist(),
    }
