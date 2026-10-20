import { create } from 'zustand';
import { api } from '../lib/api';

/** Slicer settings a profile may carry — the server filters to these too. */
export interface ProfileSettings {
  slicer_mode?: 'planar' | 'multiaxis';
  material?: string;
  layer_height?: number;
  nozzle_diameter?: number;
  print_speed?: number;
  travel_speed?: number;
  scale?: number;
  max_tilt?: number;
  infill_pattern?: string;
  infill_density?: number;
  infill_angle_base?: number;
  infill_angle_increment?: number;
}

export interface Profile {
  id: string;
  name: string;
  builtin: boolean;
  settings: ProfileSettings;
}

interface ProfilesState {
  profiles: Profile[];
  loaded: boolean;
  error: string | null;
  load: () => Promise<void>;
  save: (name: string, settings: ProfileSettings, id?: string) => Promise<Profile | null>;
  remove: (id: string) => Promise<boolean>;
}

/** Server-side material/process profiles, shared by every browser in the
 *  cell. Loaded on first use; writes refresh the list from the server so
 *  the id the server chose is what the UI shows. */
export const useProfilesStore = create<ProfilesState>()((set, get) => ({
  profiles: [],
  loaded: false,
  error: null,
  load: async () => {
    try {
      const r = await api.get<{ profiles: Profile[] }>('/profiles');
      set({ profiles: r.profiles, loaded: true, error: null });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e), loaded: true });
    }
  },
  save: async (name, settings, id) => {
    try {
      const p = await api.put<Profile>('/profiles', { name, settings, id });
      await get().load();
      return p;
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e) });
      return null;
    }
  },
  remove: async (id) => {
    try {
      await api.delete(`/profiles/${id}`);
      await get().load();
      return true;
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e) });
      return false;
    }
  },
}));
