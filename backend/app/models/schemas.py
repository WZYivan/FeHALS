"""Pydantic 数据模型（请求 / 响应 schema）。"""
from typing import List, Optional

from pydantic import BaseModel


class TrajectoryRequest(BaseModel):
    """航迹生成请求：航点列表 + 飞行高度。"""

    waypoints: List[List[float]]  # [[x, y, z], ...]
    altitude: float = 100.0


class ConfigRequest(BaseModel):
    """仿真参数配置请求。"""

    platform_type: str = "UAV"  # UAV | Airborne | Terrestrial
    speed: float = 5.0  # 飞行速度 (m/s)
    altitude: float = 100.0  # 飞行高度 (m)
    scan_freq: float = 10.0  # 扫描频率 (Hz)
    scan_angle: float = 30.0  # 扫描角度范围（±deg，半角）
    pulse_freq: float = 50.0  # 脉冲频率 (kHz)
    # 默认 XYZ：本机 helios++ 构建的 LAS 输出不可用（LASlib 打开失败），见 README。
    # LAS/LAZ 可选，需 HELIOS++ 正确链接 LASlib 后方可使用。
    output_format: str = "XYZ"  # LAS | LAZ | XYZ


class SimulationRunRequest(BaseModel):
    """仿真执行请求。"""

    trajectory_id: str
    config_id: str
    scene_model_id: Optional[str] = None


class SimulationStatus(BaseModel):
    """仿真状态。"""

    task_id: str
    status: str  # queued | running | completed | failed | cancelled
    progress: int = 0
    message: str = ""
    result_file: Optional[str] = None


class QueueTaskBrief(BaseModel):
    """队列快照中的单任务摘要。"""

    task_id: str
    status: str
    progress: int = 0
    message: str = ""
    priority: int = 0
    output_format: str = "XYZ"
    submitted_at: Optional[float] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    result_file: Optional[str] = None


class QueueSnapshot(BaseModel):
    """仿真任务队列快照。"""

    max_concurrency: int
    running_count: int
    queued_count: int
    tasks: List[QueueTaskBrief]
