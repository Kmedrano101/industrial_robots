import { useTranslation } from 'react-i18next';
import type { RobotPageController } from './useRobotPage';

/** Simulation / LIVE toggle with the reason LIVE is blocked, if it is. */
export default function ModeSelector({ c }: { c: RobotPageController }) {
  const { t } = useTranslation();
  return (
    <div
      className={`rounded-lg border px-3 py-2 ${
        c.canReallyMove
          ? 'border-red-500/50 bg-red-500/10'
          : 'border-blue-500/40 bg-blue-500/10'
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="inline-flex rounded-md bg-gray-200/60 dark:bg-gray-800/60 p-0.5 gap-0.5">
          <button
            onClick={c.disarmLive}
            className={`rounded px-3 py-1 text-xs font-semibold transition-colors ${
              !c.liveArmed
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
            }`}
          >
            {t('test.modeSim')}
          </button>
          <button
            onClick={c.armLive}
            disabled={!c.liveAvailable}
            title={c.liveBlockedReason ?? undefined}
            className={`rounded px-3 py-1 text-xs font-semibold transition-colors ${
              c.liveArmed
                ? 'bg-red-600 text-white shadow-sm'
                : c.liveAvailable
                ? 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
                : 'text-gray-400 dark:text-gray-600 cursor-not-allowed'
            }`}
          >
            {t('test.modeLiveRobot')}
          </button>
        </div>
        {!c.liveArmed && c.connected && (
          <button
            onClick={c.syncSimFromRobot}
            className="shrink-0 rounded-md border border-blue-500/50 px-2 py-1 text-[11px] font-medium text-blue-600 dark:text-blue-400 hover:bg-blue-500/10"
          >
            {t('test.syncFromRobot')}
          </button>
        )}
      </div>
      <p
        className={`mt-1.5 text-[11px] ${
          c.canReallyMove
            ? 'font-semibold text-red-600 dark:text-red-400'
            : 'text-blue-600 dark:text-blue-400'
        }`}
      >
        {c.canReallyMove
          ? `⚠ ${t('test.liveModeHint')}`
          : c.liveBlockedReason
          ? `${t('test.liveBlocked')}: ${c.liveBlockedReason}`
          : t('test.simulationModeHint')}
      </p>
    </div>
  );
}
