import { useTranslation } from 'react-i18next';
import Card from '../common/Card';
import Badge from '../common/Badge';
import ThemeToggle from '../common/ThemeToggle';
import LanguageSwitch from '../common/LanguageSwitch';
import { Segmented } from '../common/Field';
import { useSettingsStore, type RobotModel } from '../../stores/useSettingsStore';
import { useRobotStore } from '../../stores/useRobotStore';
import { ROBOT_MODELS } from '../robot/robotConstants';
import pkg from '../../../package.json';

function Row({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2 border-b border-line py-3 last:border-b-0 sm:flex-row sm:items-center sm:justify-between sm:gap-6">
      <div className="min-w-0">
        <div className="text-sm font-medium">{label}</div>
        {hint && <div className="mt-0.5 text-xs text-muted">{hint}</div>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="inline-flex min-h-touch cursor-pointer select-none items-center gap-3 text-sm">
      <span className="relative inline-flex h-6 w-11 shrink-0 items-center">
        <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="peer sr-only" />
        <span className="absolute inset-0 rounded-full bg-line transition-colors peer-checked:bg-accent" />
        <span className="absolute left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform peer-checked:translate-x-5" />
      </span>
      <span className="sr-only">{label}</span>
    </label>
  );
}

const SHORTCUTS: [string, string][] = [
  ['1 · 2 · 3 · 4', 'settings.shortcutPages'],
  ['Space', 'settings.shortcutPause'],
  ['↑ / ↓', 'settings.shortcutLayers'],
];

export default function SettingsPage() {
  const { t } = useTranslation();
  const robotModel = useSettingsStore((s) => s.robotModel);
  const setRobotModel = useSettingsStore((s) => s.setRobotModel);
  const splitView = useSettingsStore((s) => s.robotSplitView);
  const setSplitView = useSettingsStore((s) => s.setRobotSplitView);
  const backendUrType = useRobotStore((s) => s.urType);
  const backendConnected = useRobotStore((s) => s.connected);
  const robotConnected = useRobotStore((s) => s.robotConnected);
  const testPanelEnabled = useRobotStore((s) => s.testPanelEnabled);

  const mismatch = Boolean(backendUrType) && backendUrType.toLowerCase() !== robotModel;

  return (
    <div className="scroll-thin flex-1 overflow-y-auto bg-bg p-4 sm:p-6">
      <div className="mx-auto max-w-3xl space-y-4">
        <h2 className="text-lg font-semibold tracking-tight">{t('settings.title')}</h2>

        <Card title={t('settings.appearance')}>
          <Row label={t('settings.theme')}>
            <ThemeToggle />
          </Row>
          <Row label={t('settings.language')}>
            <LanguageSwitch />
          </Row>
        </Card>

        <Card title={t('settings.robot')}>
          <Row
            label={t('settings.robotModel')}
            hint={
              backendUrType
                ? `${t('test.backendUrType')}: ${backendUrType}${mismatch ? ` — ${t('test.modelMismatch')}` : ''}`
                : t('settings.robotModelHint')
            }
          >
            <Segmented<RobotModel>
              value={robotModel}
              onChange={setRobotModel}
              size="sm"
              className="flex-wrap"
              options={ROBOT_MODELS.map((m) => ({ value: m.value, label: m.label }))}
              aria-label={t('settings.robotModel')}
            />
          </Row>
          <Row label={t('test.splitView')} hint={t('settings.splitViewHint')}>
            <Toggle checked={splitView} onChange={setSplitView} label={t('test.splitView')} />
          </Row>
        </Card>

        <Card title={t('settings.backend')}>
          <Row label={t('settings.backendConnection')}>
            <Badge severity={backendConnected ? 'ok' : 'warn'} dot>
              {backendConnected ? t('live.connected') : t('live.disconnected')}
            </Badge>
          </Row>
          <Row label={t('live.connection')}>
            <Badge severity={robotConnected ? 'ok' : 'neutral'} dot>
              {robotConnected ? t('live.connected') : t('live.disconnected')}
            </Badge>
          </Row>
          <Row label={t('settings.testPanel')} hint={t('settings.testPanelHint')}>
            <Badge severity={testPanelEnabled ? 'warn' : 'neutral'} mono>
              {testPanelEnabled ? 'ENABLE_TEST_PANEL=true' : 'ENABLE_TEST_PANEL=false'}
            </Badge>
          </Row>
        </Card>

        <Card title={t('settings.shortcuts')}>
          <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
            {SHORTCUTS.map(([keys, label]) => (
              <div key={keys} className="contents">
                <dt>
                  <kbd className="rounded border border-line bg-surface2 px-1.5 py-0.5 font-mono text-xs text-ink">{keys}</kbd>
                </dt>
                <dd className="text-muted">{t(label)}</dd>
              </div>
            ))}
          </dl>
        </Card>

        <Card title={t('settings.about')}>
          <div className="flex flex-wrap items-center gap-6">
            <img src="/tidop_logo.png" alt="TIDOP" className="h-8 w-auto object-contain" />
            <img src="/zamora_futurelab.svg" alt="Zamora FutureLab" className="h-9 w-auto object-contain dark:invert" />
          </div>
          <p className="mt-3 text-xs text-muted">
            {t('header.title')} · {t('settings.version')} {pkg.version}
          </p>
        </Card>
      </div>
    </div>
  );
}
