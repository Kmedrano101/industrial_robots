import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type Theme = 'dark' | 'light' | 'system';
/** Top-level pages, one per navigation entry:
 *  - prepare:  3D bed + import/slice/print panel
 *  - monitor:  live robot + telemetry/progress panel
 *  - jobs:     print history
 *  - robot:    commissioning, jog, dashboard commands
 *  - settings: appearance, robot model, about */
export type AppPage = 'prepare' | 'monitor' | 'jobs' | 'robot' | 'settings';
/** Camera/scale mode of the printer viewer, implied by the page. Kept as a
 *  type because SceneCanvas and its children branch on it. */
export type ViewMode = 'prepare' | 'live';
export type RobotModel = 'ur3e' | 'ur5e' | 'ur7e' | 'ur10e' | 'ur16e' | 'ur20' | 'ur30';

export function viewModeForPage(page: AppPage): ViewMode {
  return page === 'monitor' ? 'live' : 'prepare';
}

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

/** Persisted-shape upgrades. Exported for tests. */
export function migrateSettings(persisted: unknown, version: number): Partial<SettingsState> {
  const s = (persisted ?? {}) as Record<string, unknown>;
  if (version < 1 && s.viewMode === 'test') {
    // v0: the Test panel lived in the viewer toggle before the Robot page.
    s.viewMode = 'prepare';
    s.page = 'robot';
  }
  if (version < 2) {
    // v1: `page` was 'printer' | 'robot' with a separate `viewMode`
    // ('prepare' | 'live'). The two printer views are now pages.
    if (s.page === 'printer' || s.page === undefined) {
      s.page = s.viewMode === 'live' ? 'monitor' : 'prepare';
    }
    delete s.viewMode;
  }
  return s as Partial<SettingsState>;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      theme: 'dark',
      language: 'es',
      page: 'prepare' as AppPage,
      robotModel: 'ur5e' as RobotModel,
      robotSplitView: false,
      robotCameraView: null,
      setTheme: (theme) => {
        applyTheme(theme);
        set({ theme });
      },
      setLanguage: (language) => set({ language }),
      setPage: (page) => set({ page }),
      setRobotModel: (robotModel) => set({ robotModel }),
      setRobotSplitView: (robotSplitView) => set({ robotSplitView }),
      setRobotCameraView: (robotCameraView) => set({ robotCameraView }),
    }),
    {
      name: 'ur-3d-printer-settings',
      version: 2,
      migrate: (persisted, version) => migrateSettings(persisted, version) as SettingsState,
      onRehydrateStorage: () => (state) => {
        if (state) applyTheme(state.theme);
      },
    },
  ),
);
