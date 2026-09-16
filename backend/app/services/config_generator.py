"""生成 HELIOS++ 所需的场景 XML 与扫描任务（survey）XML。

HELIOS++ 的仿真输入是一个 survey XML，它引用：
  - scene XML（含 OBJ 模型，objloader 滤镜加载）
  - 平台目录（data/platforms.xml#...）与扫描器目录（data/scanners_*.xml#...）
  - 航迹文件（.trj）
这些 data/... 相对引用通过 `helios++ --assets <dir>` 解析。
"""
import json
import math
import time
import xml.sax.saxutils as sx
from pathlib import Path
from typing import Optional, Tuple

from app.config import CONFIGS_DIR

# 扫描器 ID → (XML 文件名, HELIOS++ 引用 ID)
# 数据源：3rd/helios/python/pyhelios/data/{scanners_als,scanners_tls}.xml
SCANNER_FILE_MAP = {
    # ALS 扫描仪
    "riegl_vux-1uav": ("scanners_als.xml", "riegl_vux-1uav"),
    "riegl_vq_780i": ("scanners_als.xml", "riegl_vq_780i"),
    "riegl_vq-1560i": ("scanners_als.xml", "riegl_vq-1560i"),
    "leica_als50": ("scanners_als.xml", "leica_als50"),
    "riegl_lms-q780": ("scanners_als.xml", "riegl_lms-q780"),
    "optech_galaxy": ("scanners_als.xml", "optech_galaxy"),
    "dji-zenmuse-l2-repetitive": ("scanners_als.xml", "dji-zenmuse-l2-repetitive"),
    # TLS/MLS 扫描仪
    "vlp16": ("scanners_tls.xml", "vlp16"),
    "velodyne_hdl-64e": ("scanners_tls.xml", "velodyne_hdl-64e"),
    "riegl_vz400": ("scanners_tls.xml", "riegl_vz400"),
    "livox-avia-non-repetitive": ("scanners_tls.xml", "livox-avia-non-repetitive"),
}

# 静态平台（TLS 三脚架，type="static"）：无轨迹，固定坐标扫描
STATIC_PLATFORMS = {"tripod", "tripod_down"}

# 地面车载平台（MLS，type="linearpath" 但 onGround）：逐航点 leg，无 interpolated
GROUND_PLATFORMS = {"vehicle_linearpath"}

# 360° 旋转 LiDAR（optics=rotating 且 scanFreq=0）：需显式头部转动，否则只扫单方向
# 转头转速 = 扫描频率(Hz) × 360（deg/s）
SPINNING_SCANNERS = {"vlp16", "velodyne_hdl-64e"}

# 转镜振荡 + 头部水平摆扫（pan）的地基扫描仪：scanner_id -> 转头转速 (deg/s)
# RIEGL VZ-400 的 headRotatePerSecMax=60°/s，取 10°/s 与官方示例 tls_toyblocks.xml 一致
PANNING_SCANNERS = {"riegl_vz400": 10.0}

# 无模型时的默认地面场景（通过 --assets 仓库根目录解析）
_DEFAULT_GROUNDPLANE = "data/sceneparts/basic/groundplane/groundplane.obj"

# config_id -> 参数 dict（进程内注册表，另落盘 JSON 便于跨进程恢复）
_CONFIG_REGISTRY: dict = {}


def _esc(s: object) -> str:
    return sx.escape(str(s))


def store_config(params: dict) -> str:
    """保存配置参数，返回 config_id。"""
    config_id = f"cfg_{int(time.time() * 1000)}"
    _CONFIG_REGISTRY[config_id] = dict(params)
    (CONFIGS_DIR / f"{config_id}.json").write_text(
        json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return config_id


def get_config(config_id: str) -> dict:
    """按 id 读取配置参数。"""
    if config_id in _CONFIG_REGISTRY:
        return _CONFIG_REGISTRY[config_id]
    p = CONFIGS_DIR / f"{config_id}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    raise KeyError(f"配置不存在：{config_id}")


def detect_up_axis(obj_path: str) -> str:
    """从 OBJ 顶点包围盒推断 up 轴（'y' 或 'z'）。

    启发式：模型通常“坐落”在地面上，其 up 轴的最小坐标最接近 0。
    返回 'y' 表示该模型为 Y-up（需旋转到 Z-up），否则 'z'。
    """
    mins = [float("inf")] * 3
    with open(obj_path, "r", errors="ignore") as f:
        for line in f:
            if not line.startswith("v "):
                continue
            parts = line.split()
            try:
                for i in range(3):
                    v = float(parts[i + 1])
                    if v < mins[i]:
                        mins[i] = v
            except (ValueError, IndexError):
                continue
    if mins[0] == float("inf"):
        return "z"  # 无顶点，默认 z
    grounded = [abs(m) for m in mins]
    up_idx = grounded.index(min(grounded))
    return "y" if up_idx == 1 else "z"


def generate_scene_xml(
    model_paths: Optional[list[tuple[str, str]]] = None
) -> Tuple[Path, str]:
    """生成场景 XML，返回 (xml 路径, scene_id)。

    model_paths 为 [(路径, up_轴), ...]，每个元组在场景中生成一个独立的 <part>。
    为 None 或空列表时使用默认地面平面。
    """
    scene_id = f"fehals_scene_{int(time.time() * 1000)}"
    parts = []
    if model_paths:
        for p, up in model_paths:
            up_line = f'                <param type="string" key="up" value="{up}" />\n'
            parts.append(
                "        <part>\n"
                '            <filter type="objloader">\n'
                f'                <param type="string" key="filepath" value="{_esc(p)}" />\n'
                f"{up_line}"
                "            </filter>\n"
                "        </part>\n"
            )
    else:
        parts.append(
            "        <part>\n"
            '            <filter type="objloader">\n'
            f'                <param type="string" key="filepath" value="{_DEFAULT_GROUNDPLANE}" />\n'
            "            </filter>\n"
            "        </part>\n"
        )
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<document>\n"
        f'    <scene id="{scene_id}" name="{scene_id}">\n'
        f'{"".join(parts)}'
        "    </scene>\n"
        "</document>\n"
    )
    xml_path = CONFIGS_DIR / f"scene_{scene_id}.xml"
    xml_path.write_text(content, encoding="utf-8")
    return xml_path, scene_id


def _read_trajectory_waypoints(traj_path: str) -> list[tuple[float, float]]:
    """解析 .trj 文件，返回航点 (x, y) 列表。

    .trj 列顺序：t, roll, pitch, yaw, x, y, z（索引 0-6）。
    跳过 '#' 注释行与表头。
    """
    pts: list[tuple[float, float]] = []
    try:
        with open(traj_path, "r", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(",")
                if len(parts) < 7:
                    continue
                try:
                    x = float(parts[4])
                    y = float(parts[5])
                except ValueError:
                    continue
                pts.append((x, y))
    except OSError:
        pass
    return pts


def _trajectory_duration(traj_path: str) -> float:
    """返回 .trj 文件最后一行的时间列（列 0），用于头部转动 stop 计算。"""
    dur = 0.0
    try:
        with open(traj_path, "r", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(",")
                if len(parts) < 7:
                    continue
                try:
                    dur = float(parts[0])
                except ValueError:
                    continue
    except OSError:
        pass
    return dur


def generate_survey_xml(
    scene_xml_path: str,
    scene_id: str,
    traj_path: str,
    params: dict,
) -> Path:
    """生成 survey XML，返回其路径。

    按平台类型分三种生成方式：
      - 静态平台（tripod/tripod_down）：直接引用 platform + 固定坐标，无轨迹
      - 地面车载（vehicle_linearpath）：逐航点 leg（onGround + movePerSec），无 interpolated
      - 空中平台（其余）：interpolated + basePlatform + 轨迹（原有行为）
    另对 360° 旋转 LiDAR 追加头部转动参数，避免只扫单侧。
    """
    platform_id = params.get("platform_id", "copter_linearpath")
    scanner_id = params.get("scanner_id", "riegl_vux-1uav")
    scanner_file, scanner_id_ref = SCANNER_FILE_MAP.get(
        scanner_id, ("scanners_als.xml", "riegl_vux-1uav")
    )

    # 参数映射：脉冲频率 kHz -> Hz；±半角 -> 总扫描角
    pulse_hz = float(params.get("pulse_freq", 50.0) or 50.0) * 1000.0
    scan_freq = float(params.get("scan_freq", 10.0) or 0.0)
    scan_angle_total = float(params.get("scan_angle", 30.0) or 0.0) * 2.0
    speed = float(params.get("speed", 5.0) or 5.0)

    # 360° 旋转 LiDAR：需显式头部转动
    head_rotate = None
    if scanner_id in SPINNING_SCANNERS:
        # 扫描频率(Hz) → 转头转速(°/s)；旋转 LiDAR 无镜面振荡（scanFreq=0），
        # 瞬时 FOV 固定 1°，全 360° 靠头部转动。
        head_rotate = scan_freq * 360.0
        scan_freq = 0.0
        scan_angle_total = 1.0

    # 转镜振荡 + 头部水平摆扫的地基扫描仪（如 RIEGL VZ-400）
    pan_speed = PANNING_SCANNERS.get(scanner_id)  # None 或 deg/s

    waypoints = _read_trajectory_waypoints(traj_path)
    traj_dur = _trajectory_duration(traj_path)

    survey_name = f"fehals_survey_{int(time.time() * 1000)}"

    # 公共扫描参数（scaset）
    scaset = (
        f'    <scannerSettings id="scaset" active="true" '
        f'pulseFreq_hz="{pulse_hz:g}" scanFreq_hz="{scan_freq:g}" '
        f'scanAngle_deg="{scan_angle_total:g}"'
    )
    if head_rotate:
        scaset += f' headRotatePerSec_deg="{head_rotate:g}"'
    elif pan_speed:
        scaset += f' headRotatePerSec_deg="{pan_speed:g}"'
    scaset += "/>\n"

    if platform_id in STATIC_PLATFORMS:
        # 静态平台：固定坐标，无轨迹
        x, y = waypoints[0] if waypoints else (0.0, 0.0)
        platform_attr = f'platform="data/platforms.xml#{platform_id}"'
        if head_rotate:
            # 360° 旋转 LiDAR：头部转动 1 秒（转速无关）确定扫描时长
            rot_attrs = f' headRotateStart_deg="0.0" headRotateStop_deg="{head_rotate:g}"'
            leg_attrs = ""
        elif pan_speed:
            # 转镜 + 头部摆扫（RIEGL VZ-400）：单次 360° 摆扫确定扫描时长
            rot_attrs = ' headRotateStart_deg="0.0" headRotateStop_deg="360.0"'
            leg_attrs = ""
        else:
            # 无头部转动的扫描仪（如 livox risley）：需要 maxDuration_s 限定扫描时长
            rot_attrs = ""
            leg_attrs = ' maxDuration_s="3.0"'
        leg = (
            f"        <leg{leg_attrs}>\n"
            f'            <platformSettings x="{x:.6f}" y="{y:.6f}" z="0.0"/>\n'
            f'            <scannerSettings template="scaset" trajectoryTimeInterval_s="0.05"{rot_attrs}/>\n'
            "        </leg>\n"
        )
    elif platform_id in GROUND_PLATFORMS:
        # 地面车载：逐航点 leg，onGround + movePerSec，最后一段关闭扫描
        platform_attr = f'platform="data/platforms.xml#{platform_id}"'
        legs = []
        n = len(waypoints)
        for i, (x, y) in enumerate(waypoints):
            is_last = (i == n - 1)
            active = "" if not is_last else ' active="false"'
            # 本 leg 时长（用于头部转动 stop）：到下一航点的距离 / 速度
            if head_rotate and i < n - 1:
                nx, ny = waypoints[i + 1]
                dist = math.hypot(nx - x, ny - y)
                dur = max(0.5, dist / speed)
                rot_attrs = f' headRotateStart_deg="0.0" headRotateStop_deg="{head_rotate * dur:g}"'
            else:
                rot_attrs = ""
            legs.append(
                "        <leg>\n"
                f'            <platformSettings x="{x:.6f}" y="{y:.6f}" z="0" '
                f'onGround="true" movePerSec_m="{speed:g}"/>\n'
                f'            <scannerSettings template="scaset" trajectoryTimeInterval_s="0.05"{active}{rot_attrs}/>\n'
                "        </leg>\n"
            )
        leg = "".join(legs)
    else:
        # 空中平台：interpolated + trajectory（原有行为）
        platform_attr = (
            'platform="interpolated"\n'
            f'            basePlatform="data/platforms.xml#{platform_id}"'
        )
        rot_attrs = ""
        if head_rotate:
            stop = max(head_rotate * traj_dur, 3600.0)
            rot_attrs = f' headRotateStart_deg="0.0" headRotateStop_deg="{stop:g}"'
        leg = (
            "        <leg>\n"
            "            <platformSettings\n"
            f'                trajectory="{_esc(traj_path)}"\n'
            '                tIndex="0" xIndex="4" yIndex="5" zIndex="6" '
            'rollIndex="1" pitchIndex="2" yawIndex="3"\n'
            '                slopeFilterThreshold="0.0" toRadians="true" syncGPSTime="false"\n'
            "            />\n"
            f'            <scannerSettings template="scaset" trajectoryTimeInterval_s="0.05"{rot_attrs}/>\n'
            "        </leg>\n"
        )

    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<document>\n"
        f"{scaset}"
        f'    <survey name="{survey_name}"\n'
        f'            scene="{_esc(scene_xml_path)}#{scene_id}"\n'
        f"            {platform_attr}\n"
        f'            scanner="data/{scanner_file}#{scanner_id_ref}">\n'
        f"{leg}"
        "    </survey>\n"
        "</document>\n"
    )
    xml_path = CONFIGS_DIR / f"{survey_name}.xml"
    xml_path.write_text(content, encoding="utf-8")
    return xml_path
