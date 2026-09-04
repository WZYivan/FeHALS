// HELIOS++ 扫描器与平台参数规格
// 数据来源：3rd/helios/python/pyhelios/data/{scanners_als,scanners_tls,platforms}.xml
// key 与 simStore.params 一致（speed, altitude, scan_freq, scan_angle, pulse_freq）

export const PLATFORM_SPECS = {
  UAV: {
    id: 'copter_linearpath',
    label: 'UAV（无人机）',
    type: 'linearpath',
    params: {
      speed: { label: '飞行速度', unit: 'm/s', min: 0.5, max: 50, step: 0.5, default: 5.0 },
      altitude: { label: '飞行高度', unit: 'm', min: 3, max: 500, step: 1, default: 100.0 },
    },
  },
  Airborne: {
    id: 'copter_linearpath',
    label: 'Airborne（机载）',
    type: 'linearpath',
    params: {
      speed: { label: '飞行速度', unit: 'm/s', min: 10, max: 200, step: 1, default: 50.0 },
      altitude: { label: '飞行高度', unit: 'm', min: 3, max: 5000, step: 1, default: 500.0 },
    },
  },
}

export const SCANNER_SPECS = {
  UAV: {
    id: 'riegl_vux-1uav',
    label: 'RIEGL VUX-1UAV',
    type: 'rotating',
    headRotateAxis: '(0, 0, 1)',
    params: {
      scan_freq: { label: '扫描频率', unit: 'Hz', min: 10, max: 200, step: 1, default: 10.0 },
      scan_angle: { label: '扫描角度', unit: '±deg', min: 1, max: 165, step: 1, default: 30.0, note: '最大半角 165°' },
      pulse_freq: { label: '脉冲频率', unit: 'kHz', min: 50, max: 550, step: 10, default: 50.0, note: '50,100,200,300,380,550kHz' },
      beamDivergence: { label: '光束发散角', unit: 'mrad', min: 0.1, max: 2.0, step: 0.1, default: 0.5, readonly: true },
      rangeMin: { label: '最小测程', unit: 'm', default: 3, readonly: true },
      // HELIOS++ scanners_als.xml 中 riegl_vux-1uav 未声明 rangeMax_m，运行时解析为 DBL_MAX（无测程上限）
      rangeMax: { label: '最大测程', unit: 'm', default: null, readonly: true, note: 'HELIOS++ 未声明，视为无上限' },
    },
  },
  Airborne: {
    id: 'riegl_vux-1uav',
    label: 'RIEGL VUX-1UAV',
    type: 'rotating',
    headRotateAxis: '(0, 0, 1)',
    params: {
      scan_freq: { label: '扫描频率', unit: 'Hz', min: 10, max: 200, step: 1, default: 30.0 },
      scan_angle: { label: '扫描角度', unit: '±deg', min: 1, max: 165, step: 1, default: 30.0, note: '最大半角 165°' },
      pulse_freq: { label: '脉冲频率', unit: 'kHz', min: 50, max: 550, step: 10, default: 100.0, note: '50,100,200,300,380,550kHz' },
      beamDivergence: { label: '光束发散角', unit: 'mrad', min: 0.1, max: 2.0, step: 0.1, default: 0.5, readonly: true },
      rangeMin: { label: '最小测程', unit: 'm', default: 3, readonly: true },
      // HELIOS++ scanners_als.xml 中 riegl_vux-1uav 未声明 rangeMax_m，运行时解析为 DBL_MAX（无测程上限）
      rangeMax: { label: '最大测程', unit: 'm', default: null, readonly: true, note: 'HELIOS++ 未声明，视为无上限' },
    },
  },
}

export function getParams(platformType) {
  return {
    platform: PLATFORM_SPECS[platformType] || PLATFORM_SPECS.UAV,
    scanner: SCANNER_SPECS[platformType] || SCANNER_SPECS.UAV,
  }
}