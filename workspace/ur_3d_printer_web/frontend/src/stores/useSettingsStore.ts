import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type Theme = 'dark' | 'light' | 'system';
export type ViewMode = 'prepare' | 'live';
/** Top-level page: 'printer' = 3D viewer + slice/live panels,
 *  'robot' = full-page robot configuration / test / control services. */
export type AppPage = 'printer' | 'robot';
export type RobotModel = 'ur3e' | 'ur5e' | 'ur7e' | 'ur10e' | 'ur16e' | 'ur20' | 'ur30';

/** Saved orbit-camera pose for the Robot page's 3D view. Plain arrays so it
 *  survives JSON serialisation into localStorage. */
export interface CameraView {
  position: [number, number, number];
  target: [number, number, number];
}

/** Default framing for the Robot page viewer.
 *
 *  The arm is not at the world origin: the URDF mounts it on a table at
 *  Z=0.9 m, so with the arm in its upright pose the robot occupies roughly
 *  y = 0.9 .. 1.9 in Three.js coordinates. Orbiting around the default
 *  (0,0,0) target therefore pushes the whole robot into the top of the
 *  frame with empty floor below it. Targeting mid-robot height centres it. */
export const DEFAULT_ROBOT_CAMERA_VIEW: CameraView = {
  position: [1.7, 1.9, 1.7],
  target: [0, 1.3, 0],
};

interface SettingsState {
  theme: Theme;
  language: string;
  viewMode: ViewMode;
  page: AppPage;
  robotModel: RobotModel;
  /** Robot page layout: split the page into a left 3D-view pane and a
   *  right scrollable panel column (reusing the same live/simulated robot
   *  view). Off by default -- the Robot page starts as plain panels. */
  robotSplitView: boolean;
  /** Last orbit-camera pose the operator left the Robot page viewer in.
   *  null = never adjusted, use DEFAULT_ROBOT_CAMERA_VIEW. */
  robotCameraView: CameraView | null;
  setTheme: (theme: Theme) => void;
  setLanguage: (lang: string) => void;
  setViewMode: (mode: ViewMode) => void;
  setPage: (page: AppPage) => void;
  setRobotModel: (model: RobotModel) => void;
  setRobotSplitView: (enabled: boolean) => void;
  setRobotCameraView: (view: CameraView | null) => void;
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
      page: 'printer' as AppPage,
      robotModel: 'ur5e' as RobotModel,
      robotSplitView: false,
      robotCameraView: null,
      setTheme: (theme) => {
        applyTheme(theme);
        set({ theme });
      },
      setLanguage: (language) => set({ language }),
      setViewMode: (viewMode) => set({ viewMode }),
      setPage: (page) => set({ page }),
      setRobotModel: (robotModel) => set({ robotModel }),
      setRobotSplitView: (robotSplitView) => set({ robotSplitView }),
      setRobotCameraView: (robotCameraView) => set({ robotCameraView }),
    }),
    {
      name: 'ur-3d-printer-settings',
      version: 1,
      // v0 persisted viewMode could be 'test' (it lived in the viewer toggle
      // before the Robot page existed) — map it to the new page.
      migrate: (persisted: unknown) => {
        const state = persisted as Omit<Partial<SettingsState>, 'viewMode'> & { viewMode?: string };
        if (state?.viewMode === 'test') {
          state.viewMode = 'prepare';
          state.page = 'robot';
        }
        return state as SettingsState;
      },
      onRehydrateStorage: () => (state) => {
        if (state) applyTheme(state.theme);
      },
    },
  ),
);
