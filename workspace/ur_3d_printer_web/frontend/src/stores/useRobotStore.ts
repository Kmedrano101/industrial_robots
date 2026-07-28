import { create } from 'zustand';
import type { JointStates } from '../types/ros';

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

interface RobotState {
  jointStates: JointStates;
  /** Browser <-> backend WebSocket reachability (FastAPI process alive). */
  connected: boolean;
  /** Actual robot/ROS2 presence (driver up + robot reachable), debounced by
   *  the poller so transient blips don't flicker the UI. Distinct from
   *  `connected` — the backend can be perfectly reachable while the robot
   *  itself is powered off or unplugged. */
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
  setRobotConnected: (connected: boolean) => void;
  setRobotMode: (mode: RobotModeState) => void;
  setSafetyMode: (mode: RobotModeState) => void;
  setTestPanelEnabled: (enabled: boolean) => void;
  setMotionAllowed: (allowed: boolean) => void;
  setUrType: (urType: string) => void;
  setSystem: (system: SystemState) => void;
}

export const useRobotStore = create<RobotState>()((set) => ({
  jointStates: { positions: [0, 0, 0, 0, 0, 0] },
  connected: false,
  robotConnected: false,
  robotMode: { mode: -1, mode_name: 'UNKNOWN' },
  safetyMode: { mode: 0, mode_name: 'UNKNOWN' },
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
  setConnected: (connected) => set({ connected }),
  setRobotConnected: (robotConnected) => set({ robotConnected }),
  setRobotMode: (robotMode) => set({ robotMode }),
  setSafetyMode: (safetyMode) => set({ safetyMode }),
  setTestPanelEnabled: (testPanelEnabled) => set({ testPanelEnabled }),
  setMotionAllowed: (motionAllowed) => set({ motionAllowed }),
  setUrType: (urType) => set({ urType }),
  setSystem: (system) => set({ system }),
}));
