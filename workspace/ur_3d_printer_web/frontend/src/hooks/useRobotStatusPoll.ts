import { useEffect } from 'react';
import { useRobotStore, type RobotModeState } from '../stores/useRobotStore';
import { api } from '../lib/api';

/** Fallback cadence. Everything time-sensitive (modes, program, controllers,
 *  joints) arrives over the WebSocket as it changes; this poll only carries
 *  the few server-derived fields that are not published (`motion_allowed`,
 *  `joint_states_age_s`, `test_panel_enabled`, `ur_type`) and re-syncs the
 *  rest in case a frame was missed. At 1 Hz it used to be the primary
 *  source and cost a request per second per open tab. */
export const ROBOT_STATUS_POLL_MS = 3000;

interface RobotStatusResponse {
  ros2_connected: boolean;
  ur_type: string;
  joint_states: { positions: number[] };
  robot_mode: RobotModeState;
  safety_mode: RobotModeState;
  motion_allowed: boolean;
  test_panel_enabled: boolean;
  program_running: boolean;
  joint_states_age_s: number | null;
  motion_control_enabled: boolean;
  active_trajectory_controller: string;
  nodes: Record<string, { label: string; alive: boolean }>;
}

export function applyRobotStatus(s: RobotStatusResponse): void {
  const store = useRobotStore.getState();
  store.setRobotMode(s.robot_mode);
  store.setSafetyMode(s.safety_mode);
  store.setMotionAllowed(s.motion_allowed);
  store.setTestPanelEnabled(s.test_panel_enabled);
  store.setUrType(s.ur_type ?? '');
  store.setProgramRunning(s.program_running);
  store.setJointStatesAge(s.joint_states_age_s);
  store.setControllers({
    motion_control_enabled: s.motion_control_enabled,
    active_trajectory_controller: s.active_trajectory_controller,
    list: [],
  });
  store.setNodes(s.nodes ?? {});
  if (s.joint_states?.positions?.length === 6) {
    store.setJointStates({ positions: s.joint_states.positions });
  }
}

/** Polls /api/robot/status independent of which page is mounted. */
export function useRobotStatusPoll() {
  useEffect(() => {
    let alive = true;

    async function tick() {
      try {
        const s = await api.get<RobotStatusResponse>('/robot/status');
        if (alive) applyRobotStatus(s);
      } catch {
        // Backend unreachable: fail safe. The store clears the robot
        // connection when the backend goes away, since without it we know
        // nothing about the robot.
        if (alive) useRobotStore.getState().setConnected(false);
      }
    }

    tick();
    const id = window.setInterval(tick, ROBOT_STATUS_POLL_MS);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, []);
}
