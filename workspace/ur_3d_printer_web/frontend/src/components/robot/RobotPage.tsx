import { useTranslation } from 'react-i18next';
import { useRobotStore } from '../../stores/useRobotStore';
import { useSettingsStore } from '../../stores/useSettingsStore';
import RobotJogViewer from './RobotJogViewer';
import { useRobotPage } from './useRobotPage';
import ModeSelector from './ModeSelector';
import RobotModelCard from './RobotModelCard';
import RobotStatusCard from './RobotStatusCard';
import TcpPoseCard from './TcpPoseCard';
import SystemStatusCard from './SystemStatusCard';
import ControlCommandsCard from './ControlCommandsCard';
import ManualJogCard from './ManualJogCard';
import CompareCard from './CompareCard';
import BedPointsCard from './BedPointsCard';

/** Full-page robot commissioning view: configuration, status, control
 *  services and manual test. Write endpoints are gated by
 *  ENABLE_TEST_PANEL on the backend; the page itself is always reachable
 *  so status and configuration stay available read-only.
 *
 *  All behaviour lives in useRobotPage; this file is layout only. */
export default function RobotPage() {
  const { t } = useTranslation();
  const c = useRobotPage();
  const testPanelEnabled = useRobotStore((s) => s.testPanelEnabled);
  const splitView = useSettingsStore((s) => s.robotSplitView);
  const setSplitView = useSettingsStore((s) => s.setRobotSplitView);

  // Panel groups. The classic grid and the split-view column each wrap
  // these with their own spacing, so the Card markup is never duplicated.
  const column1 = (
    <>
      <RobotModelCard />
      <RobotStatusCard />
      <TcpPoseCard pose={c.pose} />
    </>
  );
  const column2 = (
    <>
      <SystemStatusCard c={c} />
      <ControlCommandsCard c={c} />
    </>
  );
  const column3 = (
    <>
      <ManualJogCard c={c} />
      <CompareCard c={c} />
      <BedPointsCard c={c} />
    </>
  );

  // Split-view toggle — purely a layout preference, persisted in settings.
  const splitViewToggle = (
    <label className="hidden lg:inline-flex items-center gap-2 cursor-pointer select-none text-sm font-medium text-gray-700 dark:text-gray-300">
      <span className="relative inline-flex h-5 w-9 shrink-0 items-center">
        <input
          type="checkbox"
          checked={splitView}
          onChange={(e) => setSplitView(e.target.checked)}
          className="peer sr-only"
        />
        <span className="absolute inset-0 rounded-full bg-gray-300 dark:bg-gray-700 peer-checked:bg-blue-600 transition-colors" />
        <span className="absolute left-0.5 h-4 w-4 rounded-full bg-white transition-transform peer-checked:translate-x-4" />
      </span>
      {t('test.splitView')}
    </label>
  );

  return (
    <div className="flex-1 min-h-0 flex flex-col overflow-hidden bg-gray-50 dark:bg-gray-950">
      <div className="flex-shrink-0 p-4 pb-0 space-y-3">
        <div className="flex items-center justify-end">{splitViewToggle}</div>

        {!testPanelEnabled && (
          <div className="rounded-lg border border-yellow-500/40 bg-yellow-500/10 px-4 py-2 text-sm text-yellow-600 dark:text-yellow-400">
            {t('test.panelDisabled')}
          </div>
        )}
        {(c.lastMsg || c.error || c.busy) && (
          <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-4 py-2 text-sm">
            {c.busy && <span className="text-gray-500">⏳ {c.busy}…</span>}
            {c.lastMsg && !c.error && <span className="text-green-500">✓ {c.lastMsg}</span>}
            {c.error && <span className="text-red-500">✗ {c.error}</span>}
          </div>
        )}

        {!splitView && <ModeSelector c={c} />}
      </div>

      {splitView ? (
        /* Split layout: left = live/simulated robot view, right = panels in
           one scrollable column. Stacks below lg: a half-width 3D pane on a
           phone is ~200px and useless. */
        <div className="flex-1 min-h-0 flex flex-col lg:flex-row overflow-hidden">
          <div className="h-64 lg:h-full w-full lg:w-1/2 shrink-0 border-b lg:border-b-0 lg:border-r border-gray-200 dark:border-gray-800">
            <RobotJogViewer joints={c.viewerJoints} ghostJoints={c.ghostJoints} />
          </div>
          <div className="w-full lg:w-1/2 flex-1 min-h-0 overflow-y-auto p-4">
            <div className="mx-auto max-w-2xl space-y-4">
              <ModeSelector c={c} />
              {column1}
              {column2}
              {column3}
            </div>
          </div>
        </div>
      ) : (
        /* Classic layout: no 3D view, panels in a 3-column grid. */
        <div className="flex-1 min-h-0 overflow-y-auto p-4">
          <div className="mx-auto max-w-7xl">
            <div className="grid min-w-0 grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 items-start">
              <div className="space-y-4">{column1}</div>
              <div className="space-y-4">{column2}</div>
              <div className="space-y-4 md:col-span-2 xl:col-span-1">{column3}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
