import { useTranslation } from 'react-i18next';
import { Segmented } from '../common/Field';
import Button from '../common/Button';
import type { RobotPageController } from './useRobotPage';

type Mode = 'sim' | 'live';

/** Simulation / LIVE toggle with the reason LIVE is blocked, if it is.
 *  Arming LIVE goes through `armLive`, which confirms; the control itself
 *  never flips to live silently. */
export default function ModeSelector({ c }: { c: RobotPageController }) {
  const { t } = useTranslation();
  const mode: Mode = c.liveArmed ? 'live' : 'sim';

  return (
    <div
      className={`rounded-xl border px-3 py-2.5 ${
        c.canReallyMove ? 'border-danger/50 bg-danger/10' : 'border-accent/40 bg-accent/10'
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Segmented<Mode>
          value={mode}
          size="sm"
          tone={c.canReallyMove ? 'danger' : 'accent'}
          aria-label={t('test.modeSim')}
          onChange={(m) => (m === 'live' ? c.armLive() : c.disarmLive())}
          options={[
            { value: 'sim', label: t('test.modeSim') },
            {
              value: 'live',
              label: t('test.modeLiveRobot'),
              disabled: !c.liveAvailable,
              title: c.liveBlockedReason ?? undefined,
            },
          ]}
        />
        {!c.liveArmed && c.connected && (
          <Button size="sm" variant="outline" onClick={c.syncSimFromRobot}>
            {t('test.syncFromRobot')}
          </Button>
        )}
      </div>
      <p className={`mt-1.5 text-[11px] ${c.canReallyMove ? 'font-semibold text-danger' : 'text-accent'}`}>
        {c.canReallyMove
          ? `⚠ ${t('test.liveModeHint')}`
          : c.liveBlockedReason
          ? `${t('test.liveBlocked')}: ${c.liveBlockedReason}`
          : t('test.simulationModeHint')}
      </p>
    </div>
  );
}
