import { useEffect, useRef } from 'react';
import { useRobotStore, type RobotModeState } from '../stores/useRobotStore';
import { api } from '../lib/api';

// Robot connection status is debounced asymmetrically: a couple of
// consecutive confirmations are required before flipping to "connected"
// (avoids flickering "Connected"/"Disconnected" on transient poll blips),
// but any single failed check drops back to "disconnected" immediately
// (fail-safe — this gates motion commands). The retries themselves are
// invisible; only the settled state reaches the UI, never a "reconnecting"
// label.
const ROBOT_CONNECTED_STREAK_REQUIRED = 3;

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

/** Polls /api/robot/status once a second, independent of which page is
 *  mounted (Printer > Live, Robot page, ...), so robotMode / safetyMode /
 *  motionAllowed / robotConnected / joint states stay fresh everywhere. */
export function useRobotStatusPoll() {
  const streakRef = useRef(0);

  useEffect(() => {
    let alive = true;

    async function tick() {
      try {
        const s = await api.get<RobotStatusResponse>('/robot/status');
        if (!alive) return;
        const store = useRobotStore.getState();

        store.setRobotMode(s.robot_mode);
        store.setSafetyMode(s.safety_mode);
        store.setMotionAllowed(s.motion_allowed);
        store.setTestPanelEnabled(s.test_panel_enabled);
        store.setUrType(s.ur_type ?? '');

        streakRef.current = s.ros2_connected ? streakRef.current + 1 : 0;
        const nextConnected = streakRef.current >= ROBOT_CONNECTED_STREAK_REQUIRED;
        if (nextConnected !== store.robotConnected) {
          store.setRobotConnected(nextConnected);
        }

        store.setSystem({
          programRunning: s.program_running,
          jointStatesAgeS: s.joint_states_age_s,
          motionControlEnabled: s.motion_control_enabled,
          activeTrajectoryController: s.active_trajectory_controller,
          nodes: s.nodes ?? {},
        });
        if (s.joint_states?.positions?.length === 6) {
          store.setJointStates({ positions: s.joint_states.positions });
        }
      } catch {
        // Backend/status endpoint unreachable — fail safe: drop the robot
        // connection flag immediately (no streak needed to declare "lost").
        streakRef.current = 0;
        if (useRobotStore.getState().robotConnected) {
          useRobotStore.getState().setRobotConnected(false);
        }
      }
    }

    tick();
    const id = window.setInterval(tick, 1000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, []);
}
