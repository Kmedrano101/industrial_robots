import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import SystemStatus from '../status/SystemStatus';
import ModeBadge from '../robot/ModeBadge';
import { useRobotStore } from '../../stores/useRobotStore';
import { useSettingsStore } from '../../stores/useSettingsStore';
import { api } from '../../lib/api';

function EStopButton() {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState(false);

  const trigger = async () => {
    setBusy(true);
    try {
      await api.post('/robot/stop');
      setFlash(true);
      window.setTimeout(() => setFlash(false), 1500);
    } catch {
      /* keep button visible even on failure */
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      onClick={trigger}
      disabled={busy}
      aria-label={t('test.estop')}
      title={t('test.estopHint')}
      className={`inline-flex min-h-touch shrink-0 items-center gap-2 rounded-lg border-2 px-3 text-xs font-bold uppercase tracking-wide text-white transition-colors ${
        flash ? 'animate-pulse border-red-900 bg-red-700' : 'border-red-800 bg-danger hover:brightness-110'
      } disabled:opacity-60`}
    >
      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} aria-hidden="true">
        <circle cx="12" cy="12" r="10" />
        <line x1="8" y1="8" x2="16" y2="16" />
        <line x1="16" y1="8" x2="8" y2="16" />
      </svg>
      <span className="hidden sm:inline">{t('test.estop')}</span>
    </button>
  );
}

/** Title, the one status readout, robot/safety chips and the E-stop. The
 *  settings gear moved into the navigation; the second logo lives in
 *  Settings › About, so the bar stays a status bar. */
export default function TopBar() {
  const { t } = useTranslation();
  const page = useSettingsStore((s) => s.page);
  const testPanelEnabled = useRobotStore((s) => s.testPanelEnabled);
  const robotConnected = useRobotStore((s) => s.robotConnected);
  const robotMode = useRobotStore((s) => s.robotMode);
  const safetyMode = useRobotStore((s) => s.safetyMode);

  return (
    <header className="flex min-h-[56px] items-center justify-between gap-3 border-b border-line bg-surface px-3 sm:px-4">
      <div className="flex min-w-0 items-center gap-3">
        <img src="/tidop_logo.png" alt="TIDOP" className="hidden h-7 w-auto shrink-0 object-contain sm:block" />
        <img src="/futurelab_logo.png" alt="Zamora FutureLab" className="hidden h-7 w-auto shrink-0 object-contain sm:block" />
        <div className="hidden h-6 w-px bg-line sm:block" />
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="truncate text-sm font-semibold tracking-tight">{t('header.title')}</h1>
            <span className="hidden text-faint md:inline">·</span>
            <span className="hidden truncate text-sm text-muted md:inline">{t(`nav.${page}`)}</span>
          </div>
          {/* Sole status readout — backend reachability is folded into the
             derivation, so there is no separate "connection lost" notice
             that could contradict it. */}
          <SystemStatus />
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {robotConnected && (
          <div className="hidden items-center gap-1.5 md:flex">
            <ModeBadge mode={robotMode} kind="robot" />
            <ModeBadge mode={safetyMode} kind="safety" />
          </div>
        )}
        {/* E-stop — visible whenever the test panel is on. /robot/stop is
           always allowed server-side so this works even mid-print. */}
        {testPanelEnabled && <EStopButton />}
      </div>
    </header>
  );
}
