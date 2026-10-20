import { useTranslation } from 'react-i18next';
import { useSettingsStore, type AppPage } from '../../stores/useSettingsStore';
import { usePrintStore } from '../../stores/usePrintStore';
import { PrintStateEnum } from '../../types/ros';

const ICONS: Record<AppPage, JSX.Element> = {
  prepare: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 7.5l-9-5.25L3 7.5m18 0l-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9" />
    </svg>
  ),
  monitor: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5M9 11.25v1.5M12 9v3.75m3-6v6" />
    </svg>
  ),
  robot: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M11.42 15.17l-5.1 5.1a2.12 2.12 0 01-3-3l5.1-5.1m3 3l6.37-6.37a3.75 3.75 0 00-5.3-5.3l-.56.56a.75.75 0 00 0 1.06l1.06 1.06a.75.75 0 001.06 0l.53-.53m-3.16 7.52L8.42 12.17m9.75 8.08l1.5-1.5m-1.5 1.5a2.12 2.12 0 01-3 0l-2.1-2.1" />
    </svg>
  ),
  settings: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.248a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  ),
};

const PAGES: AppPage[] = ['prepare', 'monitor', 'robot', 'settings'];

/**
 * Primary navigation: a left rail on wide screens, a bottom tab bar on
 * narrow ones. The Monitor entry carries a live dot while a job runs, so
 * the operator can see from any page that the machine is busy.
 */
export default function SideNav() {
  const { t } = useTranslation();
  const page = useSettingsStore((s) => s.page);
  const setPage = useSettingsStore((s) => s.setPage);
  const printState = usePrintStore((s) => s.printState.state);
  const printing =
    printState === PrintStateEnum.PRINTING ||
    printState === PrintStateEnum.TRAVEL_MOVE ||
    printState === PrintStateEnum.LAYER_CHANGE;
  const paused = printState === PrintStateEnum.PAUSED;

  const items = PAGES.map((key) => {
    const active = page === key;
    return (
      <button
        key={key}
        type="button"
        onClick={() => setPage(key)}
        aria-current={active ? 'page' : undefined}
        title={`${t(`nav.${key}`)} (${PAGES.indexOf(key) + 1})`}
        className={`relative flex min-h-touch flex-1 flex-col items-center justify-center gap-1 rounded-lg px-1 py-1.5 text-[10px] font-medium transition-colors lg:h-14 lg:w-14 lg:flex-none ${
          active ? 'bg-accent/12 text-accent' : 'text-muted hover:bg-surface2 hover:text-ink'
        }`}
      >
        <span className="h-5 w-5 [&_svg]:h-5 [&_svg]:w-5">{ICONS[key]}</span>
        <span className="leading-none">{t(`nav.${key}`)}</span>
        {key === 'monitor' && (printing || paused) && (
          <span
            className={`absolute right-2 top-1.5 h-2 w-2 rounded-full lg:right-3 lg:top-2 ${
              paused ? 'bg-warn' : 'bg-ok animate-pulse'
            }`}
            aria-hidden="true"
          />
        )}
      </button>
    );
  });

  return (
    <>
      {/* Rail (lg and up) */}
      <nav
        aria-label={t('nav.label')}
        className="hidden lg:flex w-[72px] shrink-0 flex-col items-center gap-1 border-r border-line bg-surface px-2 py-3"
      >
        <img src="/app_logo.png" alt="" className="mb-3 h-9 w-9 rounded-lg object-contain" />
        {items}
      </nav>

      {/* Bottom bar (below lg). Safe-area padding for phones with a home
         indicator; without it the last 20px of the bar sit under it. */}
      <nav
        aria-label={t('nav.label')}
        className="fixed inset-x-0 bottom-0 z-30 flex items-stretch gap-1 border-t border-line bg-surface px-2 pt-1 pb-[max(4px,env(safe-area-inset-bottom))] lg:hidden"
      >
        {items}
      </nav>
    </>
  );
}
