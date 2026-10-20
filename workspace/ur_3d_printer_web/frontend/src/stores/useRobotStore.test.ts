import { beforeEach, describe, expect, it } from 'vitest';
import { useRobotStore } from './useRobotStore';

beforeEach(() => {
  useRobotStore.setState(useRobotStore.getInitialState());
});

describe('useRobotStore', () => {
  it('robotConnected follows the robot mode', () => {
    const s = useRobotStore.getState();
    s.setRobotMode({ mode: 5, mode_name: 'IDLE' });
    expect(useRobotStore.getState().robotConnected).toBe(true);
    s.setRobotMode({ mode: -1, mode_name: 'UNKNOWN' });
    expect(useRobotStore.getState().robotConnected).toBe(false);
  });

  it('losing the backend fails safe: robot gone, modes unknown, motion blocked', () => {
    const s = useRobotStore.getState();
    s.setConnected(true);
    s.setRobotMode({ mode: 7, mode_name: 'RUNNING' });
    s.setSafetyMode({ mode: 1, mode_name: 'NORMAL' });
    s.setMotionAllowed(true);
    s.setConnected(false);
    const r = useRobotStore.getState();
    expect(r.connected).toBe(false);
    expect(r.robotConnected).toBe(false);
    expect(r.robotMode.mode_name).toBe('UNKNOWN');
    expect(r.safetyMode.mode_name).toBe('UNKNOWN');
    expect(r.motionAllowed).toBe(false);
  });

  it('regaining the backend does not by itself claim a robot', () => {
    useRobotStore.getState().setConnected(true);
    expect(useRobotStore.getState().robotConnected).toBe(false);
  });

  it('system sub-fields update independently', () => {
    const s = useRobotStore.getState();
    s.setProgramRunning(true);
    s.setJointStatesAge(0.1);
    s.setNodes({ a: { label: 'A', alive: false } });
    const sys = useRobotStore.getState().system;
    expect(sys).toMatchObject({ programRunning: true, jointStatesAgeS: 0.1 });
    expect(sys.nodes.a.alive).toBe(false);
    expect(sys.activeTrajectoryController).toBe('none');
  });
});
