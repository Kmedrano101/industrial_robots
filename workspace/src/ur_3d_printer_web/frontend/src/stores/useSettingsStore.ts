import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type Theme = 'dark' | 'light' | 'system';
export type ViewMode = 'prepare' | 'live';

interface SettingsState {
  theme: Theme;
  language: string;
  viewMode: ViewMode;
  setTheme: (theme: Theme) => void;
  setLanguage: (lang: string) => void;
  setViewMode: (mode: ViewMode) => void;
}

function applyTheme(theme: Theme) {
  const isDark =
    theme === 'dark' ||
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.classList.toggle('dark', isDark);
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      theme: 'dark',
      language: 'es',
      viewMode: 'prepare' as ViewMode,
      setTheme: (theme) => {
        applyTheme(theme);
        set({ theme });
      },
      setLanguage: (language) => set({ language }),
      setViewMode: (viewMode) => set({ viewMode }),
    }),
    {
      name: 'ur-3d-printer-settings',
      onRehydrateStorage: () => (state) => {
        if (state) applyTheme(state.theme);
      },
    },
  ),
);
