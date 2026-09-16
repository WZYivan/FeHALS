// HELIOS++ 平台与扫描器参数规格
// 数据来源：3rd/helios/python/pyhelios/data/{scanners_als,scanners_tls,platforms}.xml
// 独立选择：平台与扫描器解耦，各平台/扫描器定义自身的参数有效范围

export const PLATFORMS = [
  {
    id: 'copter_linearpath',
    label: 'Quadrocopter UAV',
    type: 'linearpath',
    description: '四旋翼无人机（运动学模型）',
    params: {
      speed: { label: '飞行速度', unit: 'm/s', min: 0.5, max: 50, step: 0.5, default: 5.0 },
      altitude: { label: '飞行高度', unit: 'm', min: 3, max: 500, step: 1, default: 100.0 },
    },
  },
  {
    id: 'sr22',
    label: 'Cirrus SR-22',
    type: 'linearpath',
    description: '固定翼载人飞机（高空 ALS）',
    params: {
      speed: { label: '飞行速度', unit: 'm/s', min: 20, max: 200, step: 1, default: 80.0 },
      altitude: { label: '飞行高度', unit: 'm', min: 200, max: 5000, step: 1, default: 1000.0 },
    },
  },
  {
    id: 'quadcopter',
    label: 'Quadrocopter (physics)',
    type: 'multicopter',
    description: '四旋翼物理模型（阻力/推力/加减速）',
    params: {
      speed: { label: '飞行速度', unit: 'm/s', min: 0.5, max: 30, step: 0.5, default: 5.0 },
      altitude: { label: '飞行高度', unit: 'm', min: 3, max: 500, step: 1, default: 100.0 },
    },
  },
  {
    id: 'vehicle_linearpath',
    label: 'Vehicle',
    type: 'linearpath',
    description: '地面车载平台（运动学模型）',
    params: {
      speed: { label: '行驶速度', unit: 'm/s', min: 0.5, max: 30, step: 0.5, default: 5.0 },
      altitude: { label: '传感器高度', unit: 'm', min: 0.5, max: 5, step: 0.1, default: 2.4 },
    },
  },
  {
    id: 'simple_linearpath',
    label: 'Simple Linearpath',
    type: 'linearpath',
    description: '通用线性路径平台（无安装偏移）',
    params: {
      speed: { label: '运动速度', unit: 'm/s', min: 0.1, max: 100, step: 0.5, default: 5.0 },
      altitude: { label: '传感器高度', unit: 'm', min: 0.1, max: 5000, step: 1, default: 50.0 },
    },
  },
  {
    id: 'tripod',
    label: 'TLS Tripod (static)',
    type: 'static',
    description: '地面三脚架（静态扫描）',
    params: {
      altitude: { label: '架设高度', unit: 'm', min: 0.5, max: 10, step: 0.1, default: 1.5 },
    },
  },
  {
    id: 'tripod_down',
    label: 'TLS Tripod Downward',
    type: 'static',
    description: '地面三脚架朝下（静态扫描）',
    params: {
      altitude: { label: '架设高度', unit: 'm', min: 0.5, max: 10, step: 0.1, default: 1.5 },
    },
  },
]

export const SCANNERS = [
  // ── ALS（机载激光扫描）──
  {
    id: 'riegl_vux-1uav',
    heliosFile: 'scanners_als.xml',
    label: 'RIEGL VUX-1UAV',
    optics: 'rotating',
    description: '无人机 ALS 旋转镜扫描仪，±165° 宽视场',
    params: {
      scan_freq: { label: '扫描频率', unit: 'Hz', min: 10, max: 200, step: 1, default: 10.0 },
      scan_angle: { label: '扫描角度', unit: '±deg', min: 1, max: 165, step: 1, default: 30.0 },
      pulse_freq: { label: '脉冲频率', unit: 'kHz', min: 50, max: 550, step: 10, default: 50.0, note: '50,100,200,300,380,550kHz' },
      beamDivergence: { label: '光束发散角', unit: 'mrad', default: 0.5, readonly: true },
      rangeMin: { label: '最小测程', unit: 'm', default: 3, readonly: true },
      rangeMax: { label: '最大测程', unit: 'm', default: null, readonly: true, note: 'HELIOS++ 未声明，视为无上限' },
    },
  },
  {
    id: 'riegl_vq_780i',
    heliosFile: 'scanners_als.xml',
    label: 'RIEGL VQ 780i',
    optics: 'rotating',
    description: '高性能 ALS 旋转镜扫描仪，最大脉冲 1 MHz',
    params: {
      scan_freq: { label: '扫描频率', unit: 'Hz', min: 20, max: 300, step: 1, default: 20.0 },
      scan_angle: { label: '扫描角度', unit: '±deg', min: 1, max: 30, step: 1, default: 30.0 },
      pulse_freq: { label: '脉冲频率', unit: 'kHz', min: 150, max: 1000, step: 50, default: 150.0, note: '150,250,350,500,700,1000kHz' },
      beamDivergence: { label: '光束发散角', unit: 'mrad', default: 0.25, readonly: true },
      rangeMin: { label: '最小测程', unit: 'm', default: 100, readonly: true },
      rangeMax: { label: '最大测程', unit: 'm', default: null, readonly: true, note: 'HELIOS++ 未声明，视为无上限' },
    },
  },
  {
    id: 'riegl_vq-1560i',
    heliosFile: 'scanners_als.xml',
    label: 'RIEGL VQ-1560i',
    optics: 'rotating (dual)',
    description: '双通道 ALS（532nm+1064nm），最大脉冲 2 MHz',
    params: {
      scan_freq: { label: '扫描频率', unit: 'Hz', min: 40, max: 600, step: 1, default: 40.0 },
      scan_angle: { label: '扫描角度', unit: '±deg', min: 1, max: 30, step: 1, default: 30.0 },
      pulse_freq: { label: '脉冲频率', unit: 'kHz', min: 150, max: 2000, step: 50, default: 150.0, note: '150,250,350,500,700,1000,2000kHz' },
      beamDivergence: { label: '光束发散角', unit: 'mrad', default: 0.7, readonly: true },
      rangeMin: { label: '最小测程', unit: 'm', default: 100, readonly: true },
      rangeMax: { label: '最大测程', unit: 'm', default: null, readonly: true, note: 'HELIOS++ 未声明，视为无上限' },
    },
  },
  {
    id: 'leica_als50',
    heliosFile: 'scanners_als.xml',
    label: 'Leica ALS50',
    optics: 'oscillating',
    description: '经典 ALS 振荡镜扫描仪，FOV 37.5°',
    params: {
      scan_freq: { label: '扫描频率', unit: 'Hz', min: 25, max: 70, step: 1, default: 30.0 },
      scan_angle: { label: '扫描角度', unit: '±deg', min: 1, max: 37.5, step: 0.5, default: 18.75 },
      pulse_freq: { label: '脉冲频率', unit: 'kHz', min: 83, max: 83, step: 1, default: 83.0, readonly: true },
      beamDivergence: { label: '光束发散角', unit: 'mrad', default: 0.33, readonly: true },
      rangeMin: { label: '最小测程', unit: 'm', default: 200, readonly: true },
      rangeMax: { label: '最大测程', unit: 'm', default: null, readonly: true, note: 'HELIOS++ 未声明，视为无上限' },
    },
  },
  {
    id: 'riegl_lms-q780',
    heliosFile: 'scanners_als.xml',
    label: 'RIEGL LMS-Q780',
    optics: 'rotating',
    description: 'ALS 旋转镜扫描仪，有效 FOV 60°',
    params: {
      scan_freq: { label: '扫描频率', unit: 'Hz', min: 10, max: 200, step: 1, default: 20.0 },
      scan_angle: { label: '扫描角度', unit: '±deg', min: 1, max: 30, step: 1, default: 30.0 },
      pulse_freq: { label: '脉冲频率', unit: 'kHz', min: 100, max: 400, step: 10, default: 100.0, note: '100,200,300,400kHz' },
      beamDivergence: { label: '光束发散角', unit: 'mrad', default: 0.25, readonly: true },
      rangeMin: { label: '最小测程', unit: 'm', default: 50, readonly: true },
      rangeMax: { label: '最大测程', unit: 'm', default: null, readonly: true, note: 'HELIOS++ 未声明，视为无上限' },
    },
  },
  {
    id: 'optech_galaxy',
    heliosFile: 'scanners_als.xml',
    label: 'Optech Galaxy',
    optics: 'oscillating',
    description: '长测程 ALS 振荡镜扫描仪，最大 8 回波',
    params: {
      scan_freq: { label: '扫描频率', unit: 'Hz', min: 0, max: 120, step: 1, default: 30.0 },
      scan_angle: { label: '扫描角度', unit: '±deg', min: 1, max: 30, step: 0.5, default: 15.0 },
      pulse_freq: { label: '脉冲频率', unit: 'kHz', min: 35, max: 550, step: 10, default: 35.0, note: '35,550kHz' },
      beamDivergence: { label: '光束发散角', unit: 'mrad', default: 0.354, readonly: true },
      rangeMin: { label: '最小测程', unit: 'm', default: 150, readonly: true },
      rangeMax: { label: '最大测程', unit: 'm', default: null, readonly: true, note: 'HELIOS++ 未声明，视为无上限' },
    },
  },
  {
    id: 'dji-zenmuse-l2-repetitive',
    heliosFile: 'scanners_als.xml',
    label: 'DJI Zenmuse L2 (rep.)',
    optics: 'risley',
    description: 'DJI L2 重复扫描模式，FOV 约 70°',
    params: {
      scan_freq: { label: '扫描频率', unit: 'Hz', default: null, readonly: true, note: '棱镜旋转式，非传统线扫描' },
      scan_angle: { label: '扫描角度', unit: '±deg', default: null, readonly: true, note: '棱镜决定扫描模式，不支持半角配置' },
      pulse_freq: { label: '脉冲频率', unit: 'kHz', min: 40, max: 40, step: 1, default: 40.0, readonly: true },
      beamDivergence: { label: '光束发散角', unit: 'mrad', default: 0.34, readonly: true },
      rangeMin: { label: '最小测程', unit: 'm', default: 2, readonly: true },
      rangeMax: { label: '最大测程', unit: 'm', default: null, readonly: true, note: 'HELIOS++ 未声明，视为无上限' },
    },
  },
  // ── TLS/MLS（地面/车载激光扫描）──
  {
    id: 'vlp16',
    heliosFile: 'scanners_tls.xml',
    label: 'Velodyne VLP-16',
    optics: 'rotating (16ch)',
    description: '16 通道旋转式激光雷达，垂直 FOV 30°',
    params: {
      scan_freq: { label: '扫描频率', unit: 'Hz', min: 5, max: 20, step: 1, default: 10, note: '即转头转速（5~20 Hz = 1800~7200°/s）' },
      scan_angle: { label: '扫描角度', unit: '±deg', default: null, readonly: true, note: '多通道固定 ±15° 垂直视场' },
      pulse_freq: { label: '脉冲频率', unit: 'kHz', min: 18.75, max: 18.75, step: 1, default: 18.75, readonly: true },
      beamDivergence: { label: '光束发散角', unit: 'mrad', default: 0.7, readonly: true },
      rangeMin: { label: '最小测程', unit: 'm', default: 0.1, readonly: true },
      rangeMax: { label: '最大测程', unit: 'm', default: 100, readonly: true },
    },
  },
  {
    id: 'velodyne_hdl-64e',
    heliosFile: 'scanners_tls.xml',
    label: 'Velodyne HDL-64E',
    optics: 'rotating (64ch)',
    description: '64 通道旋转式激光雷达，垂直 FOV 26.8°',
    params: {
      scan_freq: { label: '扫描频率', unit: 'Hz', min: 5, max: 15, step: 1, default: 10, note: '即转头转速（5~15 Hz = 1800~5400°/s）' },
      scan_angle: { label: '扫描角度', unit: '±deg', default: null, readonly: true, note: '64 通道固定垂直视场' },
      pulse_freq: { label: '脉冲频率', unit: 'kHz', min: 20.833, max: 20.833, step: 1, default: 20.833, readonly: true },
      beamDivergence: { label: '光束发散角', unit: 'mrad', default: 3.4, readonly: true },
      rangeMin: { label: '最小测程', unit: 'm', default: 0.9, readonly: true },
      rangeMax: { label: '最大测程', unit: 'm', default: 120, readonly: true },
    },
  },
  {
    id: 'riegl_vz400',
    heliosFile: 'scanners_tls.xml',
    label: 'RIEGL VZ-400',
    optics: 'rotating',
    description: 'TLS 旋转镜扫描仪，有效 FOV 100°',
    params: {
      scan_freq: { label: '扫描频率', unit: 'Hz', min: 3, max: 120, step: 1, default: 10.0 },
      scan_angle: { label: '扫描角度', unit: '±deg', min: 1, max: 50, step: 1, default: 30.0 },
      pulse_freq: { label: '脉冲频率', unit: 'kHz', min: 100, max: 300, step: 10, default: 100.0, note: '100,300kHz' },
      beamDivergence: { label: '光束发散角', unit: 'mrad', default: 0.3, readonly: true },
      rangeMin: { label: '最小测程', unit: 'm', default: 1.5, readonly: true },
      rangeMax: { label: '最大测程', unit: 'm', default: null, readonly: true, note: 'HELIOS++ 未声明，视为无上限' },
    },
  },
  {
    id: 'livox-avia-non-repetitive',
    heliosFile: 'scanners_tls.xml',
    label: 'Livox Avia (non-rep.)',
    optics: 'risley',
    description: '固态棱镜式非重复扫描 LiDAR，FOV 70.4°',
    params: {
      scan_freq: { label: '扫描频率', unit: 'Hz', default: null, readonly: true, note: '棱镜旋转式，非传统线扫描' },
      scan_angle: { label: '扫描角度', unit: '±deg', default: null, readonly: true, note: '棱镜决定扫描模式，不支持半角配置' },
      pulse_freq: { label: '脉冲频率', unit: 'kHz', min: 40, max: 40, step: 1, default: 40.0, readonly: true },
      beamDivergence: { label: '光束发散角', unit: 'mrad', default: 0.89, readonly: true },
      rangeMin: { label: '最小测程', unit: 'm', default: 1, readonly: true },
      rangeMax: { label: '最大测程', unit: 'm', default: null, readonly: true, note: 'HELIOS++ 未声明，视为无上限' },
    },
  },
]

export function getPlatform(id) {
  return PLATFORMS.find((p) => p.id === id) || PLATFORMS[0]
}

export function getScanner(id) {
  return SCANNERS.find((s) => s.id === id) || SCANNERS[0]
}