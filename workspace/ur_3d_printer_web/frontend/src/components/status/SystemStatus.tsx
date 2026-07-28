import { useTranslation } from 'react-i18next';
import { usePrintStore } from '../../stores/usePrintStore';
import { useRobotStore } from '../../stores/useRobotStore';
import {
  deriveSystemStatus,
  SEVERITY_DOT,
  SEVERITY_TEXT,
} from '../../lib/status';

interface SystemStatusProps {
  /** `compact` is the one-line header readout; `detailed` adds the
   *  contributing signals for the side panel. Both derive from the same
   *  computation so they can never disagree. */
  variant?: 'compact' | 'detailed';
}

/**
 * The single status readout. Replaces the old pairing of a bare print-state
 * indicator in the header with a separate connection card in the panel,
 * which could (and did) show "Ready" in green next to "Disconnected" in red.
 */
export default function SystemStatus({ variant = 'compact' }: SystemStatusProps) {
  const { t } = useTranslation();
  const printState = usePrintStore((s) => s.printState);
  const backendConnected = useRobotStore((s) => s.connected);
  const robotConnected = useRobotStore((s) => s.robotConnected);
  const safetyMode = useRobotStore((s) => s.safetyMode);
  const robotMode = useRobotStore((s) => s.robotMode);

  const status = deriveSystemStatus({
    backendConnected,
    robotConnected,
    safetyModeName: safetyMode.mode_name,
    robotModeName: robotMode.mode_name,
    printStateName: printState.state_name,
    printState: printState.state,
  });

  // aria-live so the condition is announced when it changes on its own,
  // rather than only being available to sighted users watching a dot.
  const dot = (
    <span
      className={`h-2.5 w-2.5 shrink-0 rounded-full ${SEVERITY_DOT[status.severity]}`}
      aria-hidden="true"
    />
  );
  const label = t(status.labelKey, printState.state_name);

  if (variant === 'compact') {
    return (
      <span
        className="inline-flex items-center gap-2"
        role="status"
        aria-live="polite"
      >
        {dot}
        <span className={`text-sm font-medium ${SEVERITY_TEXT[status.severity]}`}>
          {label}
        </span>
        {status.detail && (
          <span className="hidden md:inline text-xs font-mono text-gray-500">
            {status.detail}
          </span>
        )}
      </span>
    );
  }

  return (
    <div className="space-y-2" role="status" aria-live="polite">
      <div className="flex items-center gap-2">
        {dot}
        <span className={`text-sm font-semibold ${SEVERITY_TEXT[status.severity]}`}>
          {label}
        </span>
        {status.detail && (
          <span className="text-xs font-mono text-gray-500">{status.detail}</span>
        )}
      </div>

      {/* The signals the headline was derived from — shown so the operator can
         see WHY, instead of having to correlate separate widgets. */}
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs border-t border-gray-200 dark:border-gray-800 pt-2">
        <dt className="text-gray-500">{t('live.connection')}</dt>
        <dd className={`text-right font-medium ${robotConnected ? SEVERITY_TEXT.ok : SEVERITY_TEXT.neutral}`}>
          {robotConnected ? t('live.connected') : t('live.disconnected')}
        </dd>
        <dt className="text-gray-500">{t('test.safetyMode')}</dt>
        <dd className="text-right font-mono text-gray-600 dark:text-gray-300">
          {safetyMode.mode_name}
        </dd>
        <dt className="text-gray-500">{t('test.robotMode')}</dt>
        <dd className="text-right font-mono text-gray-600 dark:text-gray-300">
          {robotMode.mode_name}
        </dd>
        {/* Only claim a print state when there is a robot behind it. */}
        {status.printStateMeaningful && (
          <>
            <dt className="text-gray-500">{t('live.robotState')}</dt>
            <dd className="text-right font-medium text-gray-600 dark:text-gray-300">
              {t(`state.${printState.state_name}`, printState.state_name)}
            </dd>
          </>
        )}
      </dl>

      {printState.error_message && (
        <p className={`text-xs ${SEVERITY_TEXT.danger}`}>{printState.error_message}</p>
      )}
    </div>
  );
}
