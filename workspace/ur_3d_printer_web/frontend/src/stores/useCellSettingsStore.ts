import { create } from 'zustand';
import { api } from '../lib/api';
import type { SettingsDocument, SettingsGroup, SettingsPatch } from '../types/settings';

const RESTART_POLL_MS = 3000;
const RESTART_TIMEOUT_MS = 150_000;

interface CellSettingsState {
  doc: SettingsDocument | null;
  loading: boolean;
  saving: boolean;
  /** True from the restart request until the stack reports the saved
   *  values (or the timeout). */
  restarting: boolean;
  error: string | null;
  load: () => Promise<void>;
  save: (patch: SettingsPatch) => Promise<boolean>;
  reset: (group?: SettingsGroup) => Promise<boolean>;
  capture: (target: string) => Promise<boolean>;
  restart: () => Promise<boolean>;
  clearError: () => void;
}

function message(e: unknown): string {
  // ApiError already renders FastAPI's validation detail as "key: msg".
  return e instanceof Error ? e.message : String(e);
}

/** The cell's persistent configuration (GET/PUT /api/settings): shared by
 *  every browser, applied to the ROS stack on restart. Every write returns
 *  the full document, so the store is always the server's view. */
export const useCellSettingsStore = create<CellSettingsState>()((set, get) => {
  const apply = async (fn: () => Promise<SettingsDocument>): Promise<boolean> => {
    set({ saving: true, error: null });
    try {
      const doc = await fn();
      set({ doc, saving: false });
      return true;
    } catch (e) {
      set({ error: message(e), saving: false });
      return false;
    }
  };

  return {
    doc: null,
    loading: false,
    saving: false,
    restarting: false,
    error: null,

    load: async () => {
      set({ loading: true });
      try {
        const doc = await api.get<SettingsDocument>('/settings');
        set({ doc, loading: false, error: null });
      } catch (e) {
        set({ error: message(e), loading: false });
      }
    },

    save: (patch) => apply(() => api.put<SettingsDocument>('/settings', { patch, source: 'web' })),

    reset: (group) => apply(() => api.post<SettingsDocument>('/settings/reset', { group: group ?? null })),

    capture: (target) => apply(() => api.post<SettingsDocument>('/settings/capture', { target })),

    restart: async () => {
      set({ error: null });
      try {
        await api.post('/settings/restart');
      } catch (e) {
        set({ error: message(e) });
        return false;
      }
      set({ restarting: true });
      const started = Date.now();
      // The stack takes ~25 s to come back; keep asking until the running
      // parameters match what was saved.
      return new Promise<boolean>((resolve) => {
        const tick = async () => {
          await get().load();
          const req = get().doc?.restart_required;
          if (req === false) {
            set({ restarting: false });
            resolve(true);
          } else if (Date.now() - started > RESTART_TIMEOUT_MS) {
            set({ restarting: false, error: 'restart timeout' });
            resolve(false);
          } else {
            setTimeout(tick, RESTART_POLL_MS);
          }
        };
        setTimeout(tick, RESTART_POLL_MS);
      });
    },

    clearError: () => set({ error: null }),
  };
});
