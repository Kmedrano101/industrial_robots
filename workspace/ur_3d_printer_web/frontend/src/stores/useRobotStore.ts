import { create } from 'zustand';
import type { JointStates } from '../types/ros';

interface RobotState {
  jointStates: JointStates;
  connected: boolean;
  setJointStates: (joints: JointStates) => void;
  setConnected: (connected: boolean) => void;
}

export const useRobotStore = create<RobotState>()((set) => ({
  jointStates: { positions: [0, 0, 0, 0, 0, 0] },
  connected: false,
  setJointStates: (jointStates) => set({ jointStates }),
  setConnected: (connected) => set({ connected }),
}));
