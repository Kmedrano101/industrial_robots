import { useTranslation } from 'react-i18next';
import { useSettingsStore } from '../../stores/useSettingsStore';
import type { ViewMode } from '../../stores/useSettingsStore';
import { useRobotStore } from '../../stores/useRobotStore';

export default function ViewModeToggle() {
  const { t } = useTranslation();
  const viewMode = useSettingsStore((s) => s.viewMode);
  const setViewMode = useSettingsStore((s) => s.setViewMode);
  const connected = useRobotStore((s) => s.connected);
  const testPanelEnabled = useRobotStore((s) => s.testPanelEnabled);

  const modes: { key: ViewMode; label: string; icon: JSX.Element }[] = [
    {
      key: 'prepare',
      label: t('viewer.modePrepare'),
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.53 16.122a3 3 0 00-5.78 1.128 2.25 2.25 0 01-2.4 2.245 4.5 4.5 0 008.4-2.245c0-.399-.078-.78-.22-1.128zm0 0a15.998 15.998 0 003.388-1.62m-5.043-.025a15.994 15.994 0 011.622-3.395m3.42 3.42a15.995 15.995 0 004.764-4.648l3.876-5.814a1.151 1.151 0 00-1.597-1.597L14.146 6.32a15.996 15.996 0 00-4.649 4.763m3.42 3.42a6.776 6.776 0 00-3.42-3.42" />
        </svg>
      ),
    },
    {
      key: 'live',
      label: t('viewer.modeLive'),
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z" />
        </svg>
      ),
    },
    ...(testPanelEnabled
      ? [{
          key: 'test' as ViewMode,
          label: t('viewer.modeTest'),
          icon: (
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23-.693L5 14.5m14.8.8L20 16M5 14.5L4.2 16.3" />
            </svg>
          ),
        }]
      : []),
  ];

  return (
    <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10 flex items-center rounded-xl bg-black/60 dark:bg-black/70 backdrop-blur-md border border-white/10 p-1 gap-0.5">
      {modes.map((mode) => (
        <button
          key={mode.key}
          onClick={() => setViewMode(mode.key)}
          className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-150 ${
            viewMode === mode.key
              ? 'bg-blue-600 text-white shadow-md'
              : 'text-gray-400 hover:bg-white/10 hover:text-white'
          }`}
        >
          {mode.icon}
          <span>{mode.label}</span>
          {mode.key === 'live' && connected && (
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
