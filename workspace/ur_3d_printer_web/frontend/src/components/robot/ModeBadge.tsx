import type { RobotModeState } from '../../stores/useRobotStore';
import type { Severity } from '../../lib/status';
import Badge from '../common/Badge';

const SAFETY_BAD = [
  'PROTECTIVE_STOP',
  'SAFEGUARD_STOP',
  'SYSTEM_EMERGENCY_STOP',
  'ROBOT_EMERGENCY_STOP',
  'VIOLATION',
  'FAULT',
];

export function modeSeverity(mode: RobotModeState, kind: 'robot' | 'safety'): Severity {
  // UNKNOWN means "we have no reading", not "something is wrong": rendering
  // it in amber alongside genuine warnings made an absent value look like a
  // fault, and is the single most frequent badge on a disconnected cell.
  if (['UNKNOWN', ''].includes(mode.mode_name)) return 'neutral';
  const isOK =
    kind === 'safety'
      ? mode.mode_name === 'NORMAL'
      : ['IDLE', 'RUNNING', 'POWER_ON'].includes(mode.mode_name);
  if (isOK) return 'ok';
  const isBad =
    kind === 'safety'
      ? SAFETY_BAD.includes(mode.mode_name)
      : ['DISCONNECTED', 'NO_CONTROLLER'].includes(mode.mode_name);
  return isBad ? 'danger' : 'warn';
}

export default function ModeBadge({ mode, kind }: { mode: RobotModeState; kind: 'robot' | 'safety' }) {
  return (
    <Badge severity={modeSeverity(mode, kind)} mono dot>
      {mode.mode_name}
    </Badge>
  );
}
