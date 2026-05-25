import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type Theme = 'dark' | 'light' | 'system';
export type ViewMode = 'prepare' | 'live';
export type RobotModel = 'ur3e' | 'ur5e' | 'ur10e' | 'ur16e' | 'ur20' | 'ur30';

interface SettingsState {
  theme: Theme;
  language: string;
  viewMode: ViewMode;
  robotModel: RobotModel;
  setTheme: (theme: Theme) => void;
  setLanguage: (lang: string) => void;
  setViewMode: (mode: ViewMode) => void;
  setRobotModel: (model: RobotModel) => void;
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
      robotModel: 'ur5e' as RobotModel,
      setTheme: (theme) => {
        applyTheme(theme);
        set({ theme });
      },
      setLanguage: (language) => set({ language }),
      setViewMode: (viewMode) => set({ viewMode }),
      setRobotModel: (robotModel) => set({ robotModel }),
    }),
    {
      name: 'ur-3d-printer-settings',
      onRehydrateStorage: () => (state) => {
        if (state) applyTheme(state.theme);
      },
    },
  ),
);
