import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { usePrintStore } from '../stores/usePrintStore';
import { useRobotStore } from '../stores/useRobotStore';

/**
 * Feeds the event log from state the app already tracks.
 *
 * Deliberately app-level rather than inside the log component: the log is
 * collapsible and lives on one page, but events that happen while it is
 * closed or while the operator is on another page are exactly the ones
 * worth having afterwards.
 */
export function useEventLogger() {
  const { t } = useTranslation();
  const printStateName = usePrintStore((s) => s.printState.state_name);
  const errorMessage = usePrintStore((s) => s.printState.error_message);
  const robotConnected = useRobotStore((s) => s.robotConnected);
  const safetyModeName = useRobotStore((s) => s.safetyMode.mode_name);

  // Skip the first render of each signal: on load these hold defaults, and
  // logging them would open every session with phantom "events" that never
  // happened.
  const seeded = useRef({ print: false, robot: false, safety: false });

  useEffect(() => {
    if (!seeded.current.print) {
      seeded.current.print = true;
      return;
    }
    usePrintStore
      .getState()
      .addLogEntry('info', t('log.printState', { state: t(`state.${printStateName}`, printStateName) }));
  }, [printStateName, t]);

  useEffect(() => {
    if (!errorMessage) return;
    usePrintStore.getState().addLogEntry('error', errorMessage);
  }, [errorMessage]);

  useEffect(() => {
    if (!seeded.current.robot) {
      seeded.current.robot = true;
      return;
    }
    usePrintStore
      .getState()
      .addLogEntry(
        robotConnected ? 'info' : 'warn',
        robotConnected ? t('log.robotConnected') : t('log.robotDisconnected'),
      );
  }, [robotConnected, t]);

  useEffect(() => {
    if (!seeded.current.safety) {
      seeded.current.safety = true;
      return;
    }
    if (!safetyModeName || safetyModeName === 'UNKNOWN') return;
    const bad = safetyModeName !== 'NORMAL';
    usePrintStore
      .getState()
      .addLogEntry(bad ? 'warn' : 'info', t('log.safetyMode', { mode: safetyModeName }));
  }, [safetyModeName, t]);
}
