import { useEffect, useRef } from 'react';
import { usePrintStore } from '../stores/usePrintStore';
import { useRobotStore } from '../stores/useRobotStore';
import type { WsMessage, PrintState, PrintProgress, ExtruderState, JointStates } from '../types/ros';

const MAX_RECONNECT_DELAY = 30_000;

function getWsUrl() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/api/ws`;
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
          const msg: WsMessage = JSON.parse(event.data);
          switch (msg.topic) {
            case 'print_state':
              usePrintStore.getState().setPrintState(msg.data as unknown as PrintState);
              break;
            case 'print_progress':
              usePrintStore.getState().setPrintProgress(msg.data as unknown as PrintProgress);
              break;
            case 'extruder_state':
              usePrintStore.getState().setExtruderState(msg.data as unknown as ExtruderState);
              break;
            case 'joint_states':
              useRobotStore.getState().setJointStates(msg.data as unknown as JointStates);
              break;
            case 'heartbeat':
              // Ensure connected state stays true while receiving heartbeats
              if (!useRobotStore.getState().connected) {
                useRobotStore.getState().setConnected(true);
              }
              break;
          }
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
