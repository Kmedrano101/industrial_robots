import { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import StateIndicator from '../status/StateIndicator';
import ThemeToggle from '../common/ThemeToggle';
import LanguageSwitch from '../common/LanguageSwitch';
import { useRobotStore } from '../../stores/useRobotStore';

export default function Header() {
  const { t } = useTranslation();
  const connected = useRobotStore((s) => s.connected);
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close on click outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  return (
    <header className="flex items-center justify-between border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 px-4 py-2">
      {/* Left: logos + title + state */}
      <div className="flex items-center gap-3">
        {/* TIDOP logo */}
        <img
          src="/tidop_logo.png"
          alt="TIDOP"
          className="h-[46px] w-auto object-contain"
        />

        {/* Separator */}
        <div className="h-8 w-px bg-gray-300 dark:bg-gray-600" />

        {/* ZAMORA FUTURELAB logo */}
        <img
          src="/zamora_futurelab.svg"
          alt="Zamora FutureLab"
          className="h-9 w-auto object-contain dark:invert"
        />

        {/* Separator */}
        <div className="h-8 w-px bg-gray-300 dark:bg-gray-600" />

        {/* App title + state */}
        <div className="flex items-center gap-3">
          <h1 className="text-base font-bold hidden sm:block">{t('header.title')}</h1>
          <StateIndicator />
          {!connected && (
            <span className="text-xs text-red-500">{t('errors.connectionLost')}</span>
          )}
        </div>
      </div>

      {/* Right: settings gear */}
      <div className="relative" ref={menuRef}>
        <button
          onClick={() => setOpen(!open)}
          className="rounded-lg p-2 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          aria-label={t('settings.theme')}
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.248a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </button>

        {open && (
          <div className="absolute right-0 top-full mt-2 w-56 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-lg z-50 py-2">
            {/* Language */}
            <div className="px-4 py-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                {t('settings.language')}
              </span>
              <div className="mt-1">
                <LanguageSwitch />
              </div>
            </div>

            <hr className="border-gray-200 dark:border-gray-700 my-1" />

            {/* Theme */}
            <div className="px-4 py-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                {t('settings.theme')}
              </span>
              <div className="mt-1">
                <ThemeToggle />
              </div>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
