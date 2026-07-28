/**
 * Semantic status model — the single source of truth for "how is the system
 * doing" and for which colour that condition is allowed to use.
 *
 * Two rules drive this file, both from industrial HMI practice:
 *
 *  1. Colour is information, not decoration. Saturated colours are reserved
 *     for operating conditions; anything else stays neutral. Previously the
 *     UI used 57 distinct colour utilities and the same amber meant both
 *     "value unknown" (harmless) and "motion blocked" (operational).
 *
 *  2. There is ONE status, derived once. The header used to render the print
 *     state on its own, so it showed a green "Ready" while the panel a few
 *     centimetres away showed a red "Disconnected" — both claiming to be
 *     "the status". Severity is now computed in one place and every readout
 *     renders the same result.
 */

import { PrintStateEnum } from '../types/ros';

/** `neutral` means "no data / not applicable" — deliberately distinct from
 *  `warn`, so an unknown reading never looks like a fault. */
export type Severity = 'ok' | 'warn' | 'danger' | 'neutral';

export const SEVERITY_DOT: Record<Severity, string> = {
  ok: 'bg-emerald-500',
  warn: 'bg-amber-500',
  danger: 'bg-red-500',
  neutral: 'bg-gray-400 dark:bg-gray-600',
};

export const SEVERITY_TEXT: Record<Severity, string> = {
  ok: 'text-emerald-600 dark:text-emerald-400',
  warn: 'text-amber-600 dark:text-amber-400',
  danger: 'text-red-600 dark:text-red-400',
  neutral: 'text-gray-500 dark:text-gray-400',
};

export const SEVERITY_BADGE: Record<Severity, string> = {
  ok: 'bg-emerald-600 text-white',
  warn: 'bg-amber-500 text-black',
  danger: 'bg-red-600 text-white',
  neutral: 'bg-gray-300 dark:bg-gray-700 text-gray-700 dark:text-gray-300',
};

/** Print-state severity. Replaces the old STATE_COLORS map, which hardcoded
 *  Tailwind classes and treated transitional states as warnings. */
const PRINT_STATE_SEVERITY: Record<string, Severity> = {
  IDLE: 'neutral',        // idle is the absence of activity, not a good state
  LOADING_GCODE: 'ok',
  VALIDATING: 'ok',
  HOMING: 'ok',
  CALIBRATING: 'ok',
  PRINTING: 'ok',
  TRAVEL_MOVE: 'ok',
  LAYER_CHANGE: 'ok',
  COMPLETED: 'ok',
  PAUSED: 'warn',
  CANCELLING: 'warn',
  ERROR: 'danger',
};

export function printStateSeverity(stateName: string): Severity {
  return PRINT_STATE_SEVERITY[stateName] ?? 'neutral';
}

/** Safety modes that mean the robot is actively stopped or faulted. */
const SAFETY_DANGER = new Set([
  'PROTECTIVE_STOP',
  'SAFEGUARD_STOP',
  'SYSTEM_EMERGENCY_STOP',
  'ROBOT_EMERGENCY_STOP',
  'VIOLATION',
  'FAULT',
]);

export interface SystemStatus {
  severity: Severity;
  /** i18n key for the headline condition. */
  labelKey: string;
  /** Optional literal detail (a mode name), shown after the label. */
  detail?: string;
  /** True when the print state is meaningful — i.e. there is a robot to
   *  print with. Callers use this to avoid implying readiness. */
  printStateMeaningful: boolean;
}

export interface SystemStatusInput {
  /** Browser <-> backend WebSocket. Distinct from robotConnected: the
   *  backend can be unreachable while the robot is perfectly fine, and in
   *  that case we know nothing at all and must not claim otherwise. */
  backendConnected: boolean;
  robotConnected: boolean;
  safetyModeName: string;
  robotModeName: string;
  printStateName: string;
  printState: PrintStateEnum;
}

/**
 * Collapse everything into the single most important thing to say, in
 * severity order: losing the backend outranks everything (we are blind),
 * then an active safety stop, then a print error, then having no robot,
 * and only then the print state itself.
 */
export function deriveSystemStatus(i: SystemStatusInput): SystemStatus {
  if (!i.backendConnected) {
    return {
      severity: 'warn',
      labelKey: 'status.noBackend',
      printStateMeaningful: false,
    };
  }

  if (i.robotConnected && SAFETY_DANGER.has(i.safetyModeName)) {
    return {
      severity: 'danger',
      labelKey: 'status.safetyStop',
      detail: i.safetyModeName,
      printStateMeaningful: false,
    };
  }

  if (i.printState === PrintStateEnum.ERROR) {
    return {
      severity: 'danger',
      labelKey: 'status.printError',
      printStateMeaningful: true,
    };
  }

  // No robot: the print state is stale or default, so reporting "Ready" here
  // would be actively misleading — that is the contradiction this replaces.
  if (!i.robotConnected) {
    return {
      severity: 'neutral',
      labelKey: 'status.noRobot',
      printStateMeaningful: false,
    };
  }

  return {
    severity: printStateSeverity(i.printStateName),
    labelKey: `state.${i.printStateName}`,
    printStateMeaningful: true,
  };
}
