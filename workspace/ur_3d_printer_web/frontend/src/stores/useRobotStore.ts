import { create } from 'zustand';
import type { JointStates } from '../types/ros';

export interface RobotModeState {
  mode: number;
  mode_name: string;
}

interface RobotState {
  jointStates: JointStates;
  connected: boolean;
  robotMode: RobotModeState;
  safetyMode: RobotModeState;
  testPanelEnabled: boolean;
  motionAllowed: boolean;
  setJointStates: (joints: JointStates) => void;
  setConnected: (connected: boolean) => void;
  setRobotMode: (mode: RobotModeState) => void;
  setSafetyMode: (mode: RobotModeState) => void;
  setTestPanelEnabled: (enabled: boolean) => void;
  setMotionAllowed: (allowed: boolean) => void;
}

export const useRobotStore = create<RobotState>()((set) => ({
  jointStates: { positions: [0, 0, 0, 0, 0, 0] },
  connected: false,
  robotMode: { mode: -1, mode_name: 'UNKNOWN' },
  safetyMode: { mode: 0, mode_name: 'UNKNOWN' },
  testPanelEnabled: false,
  motionAllowed: false,
  setJointStates: (jointStates) => set({ jointStates }),
  setConnected: (connected) => set({ connected }),
  setRobotMode: (robotMode) => set({ robotMode }),
  setSafetyMode: (safetyMode) => set({ safetyMode }),
  setTestPanelEnabled: (testPanelEnabled) => set({ testPanelEnabled }),
  setMotionAllowed: (motionAllowed) => set({ motionAllowed }),
}));
