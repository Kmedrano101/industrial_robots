/** TypeScript interfaces matching ROS2 message definitions. */

export enum PrintStateEnum {
  IDLE = 0,
  LOADING_GCODE = 1,
  VALIDATING = 2,
  HOMING = 3,
  CALIBRATING = 4,
  PRINTING = 5,
  TRAVEL_MOVE = 6,
  LAYER_CHANGE = 7,
  COMPLETED = 8,
  PAUSED = 9,
  CANCELLING = 10,
  ERROR = 11,
}

export interface PrintState {
  state: PrintStateEnum;
  state_name: string;
  error_message: string;
}

export interface PrintProgress {
  current_layer: number;
  total_layers: number;
  layer_progress: number;
  overall_progress: number;
  elapsed_time: number;
  estimated_remaining: number;
  current_z_height: number;
}

export enum ExtruderStateEnum {
  OFF = 0,
  EXTRUDING = 1,
  RETRACTING = 2,
  PRIMING = 3,
  HEATING = 4,
  PURGING = 5,
  FAULT = 6,
}

export interface ExtruderState {
  state: ExtruderStateEnum;
  extrusion_rate: number;
  temperature: number;
  target_temperature: number;
  at_temperature: boolean;
  // Multi-zone telemetry (extruder_controller ≥ modular subsystem); absent
  // from older backends, hence optional.
  target_flow_mm3_s?: number;
  flow_mm3_s?: number;
  zone_temperatures?: number[];
  zone_targets?: number[];
  zone_heater_duty?: number[];
  fan_percent?: number;
  heaters_on?: boolean;
  ready?: boolean;
  fault?: string;
}

/** Static description of the mounted extruder (latched `extruder_info`
 *  topic): what the UI may offer and within which limits. */
export interface ExtruderInfo {
  name: string;
  model: string;
  kind: 'pellet_screw' | 'filament' | 'paste' | string;
  driver: string;
  nozzle_diameter_mm: number;
  zone_names: string[];
  zone_max_temperature: number[];
  min_extrusion_temperature: number;
  at_temperature_tolerance: number;
  max_flow_mm3_s: number;
  default_flow_mm3_s: number;
  has_heaters: boolean;
  has_temperature_feedback: boolean;
  has_fan: boolean;
  has_retract: boolean;
  has_purge: boolean;
  purge_volume_mm3: number;
  purge_rate_mm3_s: number;
}

export interface JointStates {
  positions: number[];
}

/** /controllers topic and the `controllers` field of the snapshot. */
export interface ControllersState {
  motion_control_enabled: boolean;
  active_trajectory_controller: string;
  list: { name: string; state: string }[];
}

/** The backend's full cached state, sent as the first WebSocket frame
 *  (`snapshot`) and by GET /api/state. Mirrors RosBridge.latest_state. */
export interface StateSnapshot {
  print_state?: PrintState;
  print_progress?: PrintProgress;
  extruder_state?: ExtruderState;
  extruder_info?: ExtruderInfo | null;
  joint_states?: JointStates;
  robot_mode?: { mode: number; mode_name: string };
  safety_mode?: { mode: number; mode_name: string };
  program_running?: boolean;
  controllers?: ControllersState;
  nodes?: Record<string, { label: string; alive: boolean }>;
}

export interface ToolpathPoint {
  x: number;
  y: number;
  z: number;
  type: 'travel' | 'extrude';
  /** Section the point belongs to. Defaults to 'perimeter' when absent. */
  kind?: 'perimeter' | 'infill';
}

export interface ToolpathLayer {
  z: number;
  index: number;
  points: ToolpathPoint[];
}

export interface WsMessage {
  topic: string;
  data: Record<string, unknown>;
  ts: number;
}
