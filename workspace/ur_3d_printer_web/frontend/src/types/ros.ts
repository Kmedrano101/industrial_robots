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
}

export interface ExtruderState {
  state: ExtruderStateEnum;
  extrusion_rate: number;
  temperature: number;
  target_temperature: number;
  at_temperature: boolean;
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
