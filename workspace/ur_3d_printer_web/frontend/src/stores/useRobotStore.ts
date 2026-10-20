import { create } from 'zustand';
import type { ControllersState, JointStates } from '../types/ros';
import { isRobotConnected } from '../lib/status';

export interface RobotModeState {
  mode: number;
  mode_name: string;
}

export interface NodeHealth {
  label: string;
  alive: boolean;
}

/** Extra system/control state surfaced for the bring-up panel (A/C/E). */
export interface SystemState {
  programRunning: boolean;
  jointStatesAgeS: number | null;
  motionControlEnabled: boolean;
  activeTrajectoryController: string;
  nodes: Record<string, NodeHealth>;
}

const UNKNOWN_ROBOT_MODE: RobotModeState = { mode: -1, mode_name: 'UNKNOWN' };
const UNKNOWN_SAFETY_MODE: RobotModeState = { mode: 0, mode_name: 'UNKNOWN' };

interface RobotState {
  jointStates: JointStates;
  /** Browser <-> backend WebSocket reachability (FastAPI process alive). */
  connected: boolean;
  /** Actual robot presence, derived from the driver's latched robot mode:
   *  anything other than UNKNOWN/DISCONNECTED means the driver is talking
   *  to a controller. Distinct from `connected` — the backend can be
   *  perfectly reachable while the robot itself is powered off or
   *  unplugged. Updated wherever the mode is, so it can never disagree
   *  with it. */
  robotConnected: boolean;
  robotMode: RobotModeState;
  safetyMode: RobotModeState;
  testPanelEnabled: boolean;
  motionAllowed: boolean;
  /** UR_TYPE the backend is actually configured for (from /robot/status),
   *  compared against the frontend's selected digital-twin model. */
  urType: string;
  system: SystemState;
  setJointStates: (joints: JointStates) => void;
  setConnected: (connected: boolean) => void;
  setRobotMode: (mode: RobotModeState) => void;
  setSafetyMode: (mode: RobotModeState) => void;
  setTestPanelEnabled: (enabled: boolean) => void;
  setMotionAllowed: (allowed: boolean) => void;
  setUrType: (urType: string) => void;
  setProgramRunning: (running: boolean) => void;
  setJointStatesAge: (ageS: number | null) => void;
  setControllers: (c: ControllersState) => void;
  setNodes: (nodes: Record<string, NodeHealth>) => void;
}

export const useRobotStore = create<RobotState>()((set) => ({
  jointStates: { positions: [0, 0, 0, 0, 0, 0] },
  connected: false,
  robotConnected: false,
  robotMode: UNKNOWN_ROBOT_MODE,
  safetyMode: UNKNOWN_SAFETY_MODE,
  testPanelEnabled: false,
  motionAllowed: false,
  urType: '',
  system: {
    programRunning: false,
    jointStatesAgeS: null,
    motionControlEnabled: false,
    activeTrajectoryController: 'none',
    nodes: {},
  },
  setJointStates: (jointStates) => set({ jointStates }),
  setConnected: (connected) =>
    connected
      ? set({ connected })
      : // Losing the backend means every robot reading is stale: drop them
        // rather than keep showing a mode we can no longer vouch for, and
        // fail safe on anything that gates motion.
        set({
          connected: false,
          robotConnected: false,
          robotMode: UNKNOWN_ROBOT_MODE,
          safetyMode: UNKNOWN_SAFETY_MODE,
          motionAllowed: false,
        }),
  setRobotMode: (robotMode) =>
    set({ robotMode, robotConnected: isRobotConnected(robotMode.mode_name) }),
  setSafetyMode: (safetyMode) => set({ safetyMode }),
  setTestPanelEnabled: (testPanelEnabled) => set({ testPanelEnabled }),
  setMotionAllowed: (motionAllowed) => set({ motionAllowed }),
  setUrType: (urType) => set({ urType }),
  setProgramRunning: (programRunning) =>
    set((s) => ({ system: { ...s.system, programRunning } })),
  setJointStatesAge: (jointStatesAgeS) =>
    set((s) => ({ system: { ...s.system, jointStatesAgeS } })),
  setControllers: (c) =>
    set((s) => ({
      system: {
        ...s.system,
        motionControlEnabled: c.motion_control_enabled,
        activeTrajectoryController: c.active_trajectory_controller,
      },
    })),
  setNodes: (nodes) => set((s) => ({ system: { ...s.system, nodes } })),
}));
