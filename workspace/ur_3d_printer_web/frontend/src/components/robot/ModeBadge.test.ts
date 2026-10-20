import { describe, expect, it } from 'vitest';
import { modeSeverity } from './ModeBadge';

describe('modeSeverity', () => {
  it('no reading is neutral, never a warning', () => {
    expect(modeSeverity({ mode: -1, mode_name: 'UNKNOWN' }, 'robot')).toBe('neutral');
    expect(modeSeverity({ mode: 0, mode_name: '' }, 'safety')).toBe('neutral');
  });

  it('robot modes', () => {
    expect(modeSeverity({ mode: 7, mode_name: 'RUNNING' }, 'robot')).toBe('ok');
    expect(modeSeverity({ mode: 0, mode_name: 'DISCONNECTED' }, 'robot')).toBe('danger');
    expect(modeSeverity({ mode: 2, mode_name: 'BOOTING' }, 'robot')).toBe('warn');
  });

  it('safety modes', () => {
    expect(modeSeverity({ mode: 1, mode_name: 'NORMAL' }, 'safety')).toBe('ok');
    expect(modeSeverity({ mode: 7, mode_name: 'ROBOT_EMERGENCY_STOP' }, 'safety')).toBe('danger');
    expect(modeSeverity({ mode: 2, mode_name: 'REDUCED' }, 'safety')).toBe('warn');
  });
});
