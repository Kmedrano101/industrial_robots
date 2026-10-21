import { beforeEach, describe, expect, it } from 'vitest';
import { applyWsMessage } from './useWebSocket';
import { useRobotStore } from '../stores/useRobotStore';
import { usePrintStore } from '../stores/usePrintStore';
import { PrintStateEnum } from '../types/ros';

const frame = (topic: string, data: Record<string, unknown>) => ({ topic, data, ts: 0 });

beforeEach(() => {
  useRobotStore.setState(useRobotStore.getInitialState());
  usePrintStore.setState({
    printState: { state: PrintStateEnum.IDLE, state_name: 'IDLE', error_message: '' },
    extruderState: { state: 0, extrusion_rate: 0, temperature: 0, target_temperature: 0, at_temperature: false },
    extruderInfo: null,
    temperatureHistory: [],
  });
});

describe('applyWsMessage', () => {
  it('applies the full snapshot sent on connect', () => {
    applyWsMessage(
      frame('snapshot', {
        print_state: { state: PrintStateEnum.PRINTING, state_name: 'PRINTING', error_message: '' },
        joint_states: { positions: [1, 2, 3, 4, 5, 6] },
        robot_mode: { mode: 7, mode_name: 'RUNNING' },
        safety_mode: { mode: 1, mode_name: 'NORMAL' },
        program_running: true,
        controllers: {
          motion_control_enabled: true,
          active_trajectory_controller: 'scaled_joint_trajectory_controller',
          list: [],
        },
        nodes: { print_node: { label: 'Print node', alive: true } },
      }),
    );
    const r = useRobotStore.getState();
    expect(usePrintStore.getState().printState.state_name).toBe('PRINTING');
    expect(r.jointStates.positions).toEqual([1, 2, 3, 4, 5, 6]);
    expect(r.robotMode.mode_name).toBe('RUNNING');
    expect(r.robotConnected).toBe(true);
    expect(r.system.programRunning).toBe(true);
    expect(r.system.motionControlEnabled).toBe(true);
    expect(r.system.nodes.print_node.alive).toBe(true);
  });

  it('ignores a snapshot joint array of the wrong length', () => {
    applyWsMessage(frame('snapshot', { joint_states: { positions: [1, 2] } }));
    expect(useRobotStore.getState().jointStates.positions).toHaveLength(6);
  });

  it('robot_mode frames update the connection flag', () => {
    applyWsMessage(frame('robot_mode', { mode: 3, mode_name: 'POWER_OFF' }));
    expect(useRobotStore.getState().robotConnected).toBe(true);
    applyWsMessage(frame('robot_mode', { mode: 0, mode_name: 'DISCONNECTED' }));
    expect(useRobotStore.getState().robotConnected).toBe(false);
  });

  it('program_running and controllers land in system state', () => {
    applyWsMessage(frame('program_running', { running: true }));
    applyWsMessage(
      frame('controllers', {
        motion_control_enabled: false,
        active_trajectory_controller: 'joint_trajectory_controller',
        list: [],
      }),
    );
    const s = useRobotStore.getState().system;
    expect(s.programRunning).toBe(true);
    expect(s.activeTrajectoryController).toBe('joint_trajectory_controller');
  });

  it('extruder frames feed the temperature trace', () => {
    applyWsMessage(
      frame('extruder_state', {
        state: 1, extrusion_rate: 1, temperature: 210, target_temperature: 215, at_temperature: false,
      }),
    );
    const h = usePrintStore.getState().temperatureHistory;
    expect(h).toHaveLength(1);
    expect(h[0]).toMatchObject({ temp: 210, target: 215 });
  });

  it('extruder_info is kept for the viewer and the panels', () => {
    expect(usePrintStore.getState().extruderInfo).toBeNull();
    applyWsMessage(frame('extruder_info', { name: 'Mahor V5 M12 PRO', model: 'mahor_v5_m12_pro', kind: 'pellet_screw', zone_names: ['nozzle', 'barrel'] }));
    expect(usePrintStore.getState().extruderInfo?.model).toBe('mahor_v5_m12_pro');
    applyWsMessage(frame('snapshot', { extruder_info: { model: 'generic_fdm', zone_names: ['hotend'] } }));
    expect(usePrintStore.getState().extruderInfo?.model).toBe('generic_fdm');
    applyWsMessage(frame('snapshot', { extruder_info: null }));
    expect(usePrintStore.getState().extruderInfo?.model).toBe('generic_fdm');
  });

  it('heartbeat restores the backend flag', () => {
    useRobotStore.getState().setConnected(false);
    applyWsMessage(frame('heartbeat', {}));
    expect(useRobotStore.getState().connected).toBe(true);
  });

  it('unknown topics are ignored', () => {
    expect(() => applyWsMessage(frame('something_else', { x: 1 }))).not.toThrow();
  });
});
