/** Application constants. */

export const STATE_COLORS: Record<string, string> = {
  IDLE: 'bg-green-500',
  LOADING_GCODE: 'bg-yellow-500',
  VALIDATING: 'bg-yellow-500',
  HOMING: 'bg-yellow-500',
  CALIBRATING: 'bg-yellow-500',
  PRINTING: 'bg-green-500',
  TRAVEL_MOVE: 'bg-green-500',
  LAYER_CHANGE: 'bg-green-500',
  COMPLETED: 'bg-green-500',
  PAUSED: 'bg-yellow-500',
  CANCELLING: 'bg-yellow-500',
  ERROR: 'bg-red-500',
};

export const DEFAULT_SLICE_SETTINGS = {
  slicer_mode: 'planar' as const,
  layer_height: 0.2,
  nozzle_diameter: 0.4,
  print_speed: 3000,
  travel_speed: 9000,
  scale: 1.0,
  max_tilt: 30.0,
};

export type MaterialType = 'pla' | 'abs' | 'petg' | 'tpu' | 'nylon' | 'resin' | 'concrete' | 'clay' | 'metal';

export interface MaterialVisual {
  color: string;
  roughness: number;
  metalness: number;
  opacity: number;
  emissive?: string;
}

export const MATERIALS: Record<MaterialType, { label_es: string; label_en: string; visual: MaterialVisual }> = {
  pla: {
    label_es: 'PLA', label_en: 'PLA',
    visual: { color: '#4fc3f7', roughness: 0.5, metalness: 0.05, opacity: 0.92 },
  },
  abs: {
    label_es: 'ABS', label_en: 'ABS',
    visual: { color: '#f5f5dc', roughness: 0.6, metalness: 0.02, opacity: 0.95 },
  },
  petg: {
    label_es: 'PETG', label_en: 'PETG',
    visual: { color: '#81c784', roughness: 0.3, metalness: 0.08, opacity: 0.85 },
  },
  tpu: {
    label_es: 'TPU (Flexible)', label_en: 'TPU (Flexible)',
    visual: { color: '#e0e0e0', roughness: 0.8, metalness: 0.0, opacity: 0.88 },
  },
  nylon: {
    label_es: 'Nylon', label_en: 'Nylon',
    visual: { color: '#f0f0f0', roughness: 0.4, metalness: 0.05, opacity: 0.9 },
  },
  resin: {
    label_es: 'Resina', label_en: 'Resin',
    visual: { color: '#ffcc80', roughness: 0.15, metalness: 0.1, opacity: 0.8 },
  },
  concrete: {
    label_es: 'Concreto', label_en: 'Concrete',
    visual: { color: '#9e9e9e', roughness: 0.95, metalness: 0.0, opacity: 1.0 },
  },
  clay: {
    label_es: 'Arcilla', label_en: 'Clay',
    visual: { color: '#d4a574', roughness: 0.9, metalness: 0.0, opacity: 1.0 },
  },
  metal: {
    label_es: 'Metal', label_en: 'Metal',
    visual: { color: '#b0bec5', roughness: 0.25, metalness: 0.85, opacity: 1.0 },
  },
};

export const API_BASE = '/api';
export const WS_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/ws`;
export const MAX_UPLOAD_SIZE = 100 * 1024 * 1024; // 100 MB
