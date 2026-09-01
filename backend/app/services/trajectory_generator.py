"""生成 HELIOS++ 兼容的航迹文件（.trj）。

HELIOS++ 原生航迹为 CSV 格式，列顺序为：
    t, roll, pitch, yaw, x, y, z
（参见 helios-demo/data/trajectories/flyandrotate.trj）
survey XML 中通过 tIndex/xIndex/yIndex/zIndex/rollIndex/pitchIndex/yawIndex 映射列。
"""
import time
from typing import List

from app.config import TRAJECTORIES_DIR

def generate(waypoints: List[List[float]], altitude: float = 100.0) -> dict:
    """将航点列表写入原生 .trj 文件。

    飞行高度为恒定值：所有航点的高程统一为 altitude，
    仅用航点的 x、y 定义水平飞行路径（ALS 常规做法）。
    返回 dict：{file_id, path, point_count}
    """
    file_id = f"traj_{int(time.time() * 1000)}"
    path = TRAJECTORIES_DIR / f"{file_id}.trj"

    lines = [
        "#TIME_COLUMN: 0",
        '#HEADER: "t", "roll", "pitch", "yaw", "x", "y", "z"',
    ]
    for i, wp in enumerate(waypoints):
        x, y = float(wp[0]), float(wp[1])
        # 时间按 1 秒间隔递增，姿态角初始为 0；高程统一为飞行高度。
        # 注意：HELIOS++ 的轨迹解析对数据行中的空格较敏感，逗号后不加空格（同 cycloid.trj）。
        lines.append(f"{i},0,0,0,{x:.6f},{y:.6f},{altitude:.6f}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"file_id": file_id, "path": str(path), "point_count": len(waypoints)}

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"file_id": file_id, "path": str(path), "point_count": len(waypoints)}
