"""生成 HELIOS++ 所需的场景 XML 与扫描任务（survey）XML。

HELIOS++ 的仿真输入是一个 survey XML，它引用：
  - scene XML（含 OBJ 模型，objloader 滤镜加载）
  - 平台目录（data/platforms.xml#...）与扫描器目录（data/scanners_*.xml#...）
  - 航迹文件（.trj）
这些 data/... 相对引用通过 `helios++ --assets <dir>` 解析。
"""
import json
import time
import xml.sax.saxutils as sx
from pathlib import Path
from typing import Optional, Tuple

from app.config import CONFIGS_DIR

# 平台类型 → HELIOS++ 平台目录项（均为 linearpath 型，配合 interpolated 运动模型）
PLATFORM_MAP = {
    "UAV": "copter_linearpath",
    "Airborne": "copter_linearpath",
}

SCANNER_MAP = {
    "UAV": ("scanners_als.xml", "riegl_vux-1uav"),
    "Airborne": ("scanners_als.xml", "riegl_vux-1uav"),
}

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


def generate_scene_xml(model_path: Optional[str], up: str = "z") -> Tuple[Path, str]:
    """生成场景 XML，返回 (xml 路径, scene_id)。

    model_path 为绝对路径时加载用户上传的 OBJ 模型（objloader 的 up 参数用于
    指示模型 up 轴，HELIOS++ 会把 'y' 旋转为 Z-up）；为 None 时使用默认地面平面。
    """
    scene_id = f"fehals_scene_{int(time.time() * 1000)}"
    if model_path:
        filepath = model_path  # 绝对路径，objloader 直接打开
    else:
        filepath = _DEFAULT_GROUNDPLANE  # 相对路径，经 --assets 解析
        up = "z"

    up_param = f'                <param type="string" key="up" value="{up}" />\n' if model_path else ""
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<document>\n"
        f'    <scene id="{scene_id}" name="{scene_id}">\n'
        "        <part>\n"
        '            <filter type="objloader">\n'
        f'                <param type="string" key="filepath" value="{_esc(filepath)}" />\n'
        f"{up_param}"
        "            </filter>\n"
        "        </part>\n"
        "    </scene>\n"
        "</document>\n"
    )
    xml_path = CONFIGS_DIR / f"scene_{scene_id}.xml"
    xml_path.write_text(content, encoding="utf-8")
    return xml_path, scene_id


def generate_survey_xml(
    scene_xml_path: str,
    scene_id: str,
    traj_path: str,
    params: dict,
) -> Path:
    """生成 survey XML，返回其路径。"""
    platform_type = params.get("platform_type", "UAV")
    platform_id = PLATFORM_MAP.get(platform_type, "copter_linearpath")
    scanner_file, scanner_id = SCANNER_MAP.get(platform_type, ("scanners_als.xml", "riegl_vq-780i"))

    # 参数映射：脉冲频率 kHz -> Hz；±半角 -> 总扫描角
    pulse_hz = float(params.get("pulse_freq", 50.0)) * 1000.0
    scan_freq = float(params.get("scan_freq", 10.0))
    scan_angle_total = float(params.get("scan_angle", 30.0)) * 2.0

    survey_name = f"fehals_survey_{int(time.time() * 1000)}"
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<document>\n"
        f'    <scannerSettings id="scaset" active="true" '
        f'pulseFreq_hz="{pulse_hz:g}" scanFreq_hz="{scan_freq:g}" scanAngle_deg="{scan_angle_total:g}"/>\n'
        f'    <survey name="{survey_name}"\n'
        f'            scene="{_esc(scene_xml_path)}#{scene_id}"\n'
        '            platform="interpolated"\n'
        f'            basePlatform="data/platforms.xml#{platform_id}"\n'
        f'            scanner="data/{scanner_file}#{scanner_id}">\n'
        "        <leg>\n"
        "            <platformSettings\n"
        f'                trajectory="{_esc(traj_path)}"\n'
        '                tIndex="0" xIndex="4" yIndex="5" zIndex="6" '
        'rollIndex="1" pitchIndex="2" yawIndex="3"\n'
        '                slopeFilterThreshold="0.0" toRadians="true" syncGPSTime="false"\n'
        "            />\n"
        '            <scannerSettings template="scaset" trajectoryTimeInterval_s="0.05"/>\n'
        "        </leg>\n"
        "    </survey>\n"
        "</document>\n"
    )
    xml_path = CONFIGS_DIR / f"{survey_name}.xml"
    xml_path.write_text(content, encoding="utf-8")
    return xml_path
