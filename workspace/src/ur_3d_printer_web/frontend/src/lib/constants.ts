/** Application constants. */

export const STATE_COLORS: Record<string, string> = {
  IDLE: 'bg-print-idle',
  LOADING_GCODE: 'bg-print-loading',
  VALIDATING: 'bg-print-loading',
  HOMING: 'bg-print-loading',
  CALIBRATING: 'bg-print-loading',
  PRINTING: 'bg-print-active',
  TRAVEL_MOVE: 'bg-print-active',
  LAYER_CHANGE: 'bg-print-active',
  COMPLETED: 'bg-print-active',
  PAUSED: 'bg-print-paused',
  CANCELLING: 'bg-print-paused',
  ERROR: 'bg-print-error',
};

export const DEFAULT_SLICE_SETTINGS = {
  slicer_mode: 'planar' as const,
  layer_height: 1.0,
  nozzle_diameter: 0.4,
  print_speed: 3000,
  travel_speed: 9000,
  scale: 1.0,
  max_tilt: 30.0,
};

export const API_BASE = '/api';
export const WS_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/ws`;
export const MAX_UPLOAD_SIZE = 100 * 1024 * 1024; // 100 MB
