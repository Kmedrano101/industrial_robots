import { describe, expect, it } from 'vitest';
import { deriveSystemStatus, isRobotConnected, printStateSeverity } from './status';
import { PrintStateEnum } from '../types/ros';

const base = {
  backendConnected: true,
  robotConnected: true,
  safetyModeName: 'NORMAL',
  robotModeName: 'RUNNING',
  printStateName: 'IDLE',
  printState: PrintStateEnum.IDLE,
};

describe('deriveSystemStatus', () => {
  it('losing the backend outranks everything, and never claims a print state', () => {
    const s = deriveSystemStatus({ ...base, backendConnected: false, printState: PrintStateEnum.ERROR });
    expect(s.labelKey).toBe('status.noBackend');
    expect(s.severity).toBe('warn');
    expect(s.printStateMeaningful).toBe(false);
  });

  it('an active safety stop is danger and carries the mode name', () => {
    const s = deriveSystemStatus({ ...base, safetyModeName: 'PROTECTIVE_STOP' });
    expect(s).toMatchObject({ severity: 'danger', labelKey: 'status.safetyStop', detail: 'PROTECTIVE_STOP' });
  });

  it('a safety stop reading is ignored when there is no robot to have one', () => {
    const s = deriveSystemStatus({ ...base, robotConnected: false, safetyModeName: 'FAULT' });
    expect(s.labelKey).toBe('status.noRobot');
  });

  it('a print error is reported before the no-robot case', () => {
    const s = deriveSystemStatus({ ...base, printState: PrintStateEnum.ERROR, printStateName: 'ERROR' });
    expect(s).toMatchObject({ severity: 'danger', labelKey: 'status.printError' });
  });

  it('without a robot the print state is not shown as Ready', () => {
    const s = deriveSystemStatus({ ...base, robotConnected: false });
    expect(s).toMatchObject({ severity: 'neutral', labelKey: 'status.noRobot', printStateMeaningful: false });
  });

  it('with a robot the print state drives the label and colour', () => {
    const s = deriveSystemStatus({ ...base, printStateName: 'PRINTING', printState: PrintStateEnum.PRINTING });
    expect(s).toMatchObject({ severity: 'ok', labelKey: 'state.PRINTING', printStateMeaningful: true });
  });
});

describe('printStateSeverity', () => {
  it('idle is neutral, paused warns, error is danger, unknown names are neutral', () => {
    expect(printStateSeverity('IDLE')).toBe('neutral');
    expect(printStateSeverity('PAUSED')).toBe('warn');
    expect(printStateSeverity('ERROR')).toBe('danger');
    expect(printStateSeverity('SOMETHING_NEW')).toBe('neutral');
  });
});

describe('isRobotConnected', () => {
  it('matches the backend rule', () => {
    expect(isRobotConnected('UNKNOWN')).toBe(false);
    expect(isRobotConnected('DISCONNECTED')).toBe(false);
    expect(isRobotConnected('')).toBe(false);
    expect(isRobotConnected('POWER_OFF')).toBe(true);
    expect(isRobotConnected('RUNNING')).toBe(true);
  });
});
