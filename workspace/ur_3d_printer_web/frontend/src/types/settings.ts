/** Cell settings as served by GET /api/settings (backend/cell_settings.py). */

export interface ExtruderSettings {
  profile: string;
  driver: '' | 'mock' | 'gcode_serial' | 'topic' | 'ur_io';
  serial_port: string;
  serial_baud: number;
}

export interface BedSettings {
  print_origin_xyz: number[];
  print_origin_rpy: number[];
  bed_tilt_rx: number;
  bed_tilt_ry: number;
  z_hop_enabled: boolean;
  z_hop_height: number;
  size_mm: number[];
}

export interface RobotSettings {
  home_joints: number[];
  tool_offset_xyz: number[];
  tool_offset_rpy: number[];
  bed_points: Record<string, number[]>;
}

export interface MotionSettings {
  max_print_velocity: number;
  max_travel_velocity: number;
  max_acceleration: number;
  corner_blend_radius: number;
  singularity_velocity_scale: number;
}

export interface CellSettings {
  version: number;
  extruder: ExtruderSettings;
  bed: BedSettings;
  robot: RobotSettings;
  motion: MotionSettings;
}

export type SettingsGroup = 'extruder' | 'bed' | 'robot' | 'motion';

export interface SettingsHistoryEntry {
  at: number;
  source: string;
  changed: string[];
}

export interface SettingsDocument {
  settings: CellSettings;
  defaults: CellSettings;
  extruder_profiles: { id: string; name: string; kind: string }[];
  /** Per node, what the running stack uses; null when it cannot be asked. */
  effective: Record<string, Record<string, unknown> | null>;
  /** null = unknown (ROS not reachable). */
  restart_required: boolean | null;
  /** `node.param` entries whose running value differs from the saved one. */
  pending: string[] | null;
  restart_requested_at: number | null;
  updated_at: number | null;
  history: SettingsHistoryEntry[];
}

/** A partial document for PUT /api/settings. */
export type SettingsPatch = { [G in SettingsGroup]?: Partial<CellSettings[G]> };

export const BED_POINT_NAMES = ['p1', 'p2', 'p3', 'p4', 'center'] as const;
export const SERIAL_BAUDS = [0, 115200, 230400, 250000, 500000, 1000000] as const;
export const DRIVERS = ['', 'mock', 'gcode_serial', 'topic', 'ur_io'] as const;
