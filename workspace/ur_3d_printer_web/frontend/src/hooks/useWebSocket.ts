import { useEffect, useRef } from 'react';
import { usePrintStore } from '../stores/usePrintStore';
import { useRobotStore, type RobotModeState } from '../stores/useRobotStore';
import type {
  WsMessage,
  PrintState,
  PrintProgress,
  ExtruderState,
  JointStates,
  ControllersState,
  StateSnapshot,
} from '../types/ros';

const MAX_RECONNECT_DELAY = 30_000;

function getWsUrl() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/api/ws`;
}

/**
 * Route one backend frame into the stores.
 *
 * Exported so it can be unit-tested without a socket. The backend publishes
 * every topic the bridge tracks; previously only four of them were handled
 * here and the robot/safety mode, program and controller state were
 * discarded, leaving a 1 Hz REST poll to carry them with up to a second of
 * lag. They are now applied the moment they arrive, and the poll is only a
 * fallback (see useRobotStatusPoll).
 */
export function applyWsMessage(msg: WsMessage): void {
  const print = usePrintStore.getState();
  const robot = useRobotStore.getState();
  switch (msg.topic) {
    case 'snapshot':
      applySnapshot(msg.data as unknown as StateSnapshot);
      break;
    case 'print_state':
      print.setPrintState(msg.data as unknown as PrintState);
      break;
    case 'print_progress':
      print.setPrintProgress(msg.data as unknown as PrintProgress);
      break;
    case 'extruder_state':
      print.setExtruderState(msg.data as unknown as ExtruderState);
      break;
    case 'joint_states':
      robot.setJointStates(msg.data as unknown as JointStates);
      break;
    case 'robot_mode':
      robot.setRobotMode(msg.data as unknown as RobotModeState);
      break;
    case 'safety_mode':
      robot.setSafetyMode(msg.data as unknown as RobotModeState);
      break;
    case 'program_running':
      robot.setProgramRunning(Boolean((msg.data as { running?: boolean }).running));
      break;
    case 'controllers':
      robot.setControllers(msg.data as unknown as ControllersState);
      break;
    case 'heartbeat':
      // Ensure connected state stays true while receiving heartbeats
      if (!robot.connected) robot.setConnected(true);
      break;
  }
}

/** The full cached state, sent once per connection. Applied field by field
 *  so a page load shows the current robot immediately instead of defaults
 *  until each topic next changes (the latched ones may never). */
function applySnapshot(s: StateSnapshot): void {
  const print = usePrintStore.getState();
  const robot = useRobotStore.getState();
  if (s.print_state) print.setPrintState(s.print_state);
  if (s.print_progress) print.setPrintProgress(s.print_progress);
  if (s.extruder_state) print.setExtruderState(s.extruder_state);
  if (s.joint_states?.positions?.length === 6) robot.setJointStates(s.joint_states);
  if (s.robot_mode) robot.setRobotMode(s.robot_mode);
  if (s.safety_mode) robot.setSafetyMode(s.safety_mode);
  if (typeof s.program_running === 'boolean') robot.setProgramRunning(s.program_running);
  if (s.controllers) robot.setControllers(s.controllers);
  if (s.nodes) robot.setNodes(s.nodes);
}

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectDelay = useRef(1000);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    function connect() {
      if (!mountedRef.current) return;
      if (wsRef.current?.readyState === WebSocket.OPEN) return;

      const ws = new WebSocket(getWsUrl());
      wsRef.current = ws;

      ws.onopen = () => {
        useRobotStore.getState().setConnected(true);
        reconnectDelay.current = 1000;
      };

      ws.onmessage = (event) => {
        try {
          applyWsMessage(JSON.parse(event.data) as WsMessage);
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        useRobotStore.getState().setConnected(false);
        if (mountedRef.current) {
          clearTimeout(reconnectTimer.current);
          reconnectTimer.current = setTimeout(() => {
            reconnectDelay.current = Math.min(reconnectDelay.current * 2, MAX_RECONNECT_DELAY);
            connect();
          }, reconnectDelay.current);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      mountedRef.current = false;
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, []);
}
