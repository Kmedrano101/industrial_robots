import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useCellSettingsStore } from './useCellSettingsStore';
import type { SettingsDocument } from '../types/settings';

const base: SettingsDocument = {
  settings: {
    version: 1,
    extruder: { profile: 'mahor_v5_m12_pro', driver: 'mock', serial_port: '', serial_baud: 0 },
    bed: { print_origin_xyz: [-0.3, 0, -0.01], print_origin_rpy: [0, 0, 0], bed_tilt_rx: 0, bed_tilt_ry: 0, z_hop_enabled: true, z_hop_height: 0.008, size_mm: [300, 300] },
    robot: { home_joints: [0, -1.57, 1.57, -1.57, -1.57, 0], tool_offset_xyz: [0, 0, 0.105], tool_offset_rpy: [0, 0, 0], bed_points: {} },
    motion: { max_print_velocity: 0.05, max_travel_velocity: 0.15, max_acceleration: 0.5, corner_blend_radius: 0.002, singularity_velocity_scale: 0.3 },
  },
  defaults: null as unknown as SettingsDocument['settings'],
  extruder_profiles: [{ id: 'mahor_v5_m12_pro', name: 'Mahor V5 M12 PRO', kind: 'pellet_screw' }],
  effective: { print_node: null, extruder_controller: null },
  restart_required: null,
  pending: null,
  restart_requested_at: null,
  updated_at: null,
  history: [],
};
base.defaults = base.settings;

function mockFetch(responder: (url: string, init?: RequestInit) => unknown) {
  const calls: { url: string; body?: unknown; method: string }[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ url, body, method: init?.method ?? 'GET' });
    const r = responder(url, init);
    if (r instanceof Response) return r;
    return new Response(JSON.stringify(r), { status: 200, headers: { 'Content-Type': 'application/json' } });
  }));
  return calls;
}

beforeEach(() => {
  useCellSettingsStore.setState({ doc: null, loading: false, saving: false, restarting: false, error: null });
  vi.useFakeTimers();
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe('useCellSettingsStore', () => {
  it('load fills the document', async () => {
    mockFetch(() => base);
    await useCellSettingsStore.getState().load();
    expect(useCellSettingsStore.getState().doc?.settings.motion.max_print_velocity).toBe(0.05);
  });

  it('save sends the group patch and keeps the server document', async () => {
    const calls = mockFetch(() => ({ ...base, restart_required: true, pending: ['print_node.max_travel_velocity'] }));
    const ok = await useCellSettingsStore.getState().save({ motion: { max_travel_velocity: 0.2 } });
    expect(ok).toBe(true);
    expect(calls[0].method).toBe('PUT');
    expect(calls[0].body).toEqual({ patch: { motion: { max_travel_velocity: 0.2 } }, source: 'web' });
    expect(useCellSettingsStore.getState().doc?.pending).toEqual(['print_node.max_travel_velocity']);
  });

  it('validation errors are surfaced with their key and leave the document alone', async () => {
    mockFetch(() => new Response(JSON.stringify({ detail: [{ loc: 'motion.max_acceleration', msg: 'too big' }] }), {
      status: 422, headers: { 'Content-Type': 'application/json' },
    }));
    useCellSettingsStore.setState({ doc: base });
    const ok = await useCellSettingsStore.getState().save({ motion: { max_acceleration: 99 } });
    expect(ok).toBe(false);
    expect(useCellSettingsStore.getState().error).toContain('motion.max_acceleration');
    expect(useCellSettingsStore.getState().doc).toBe(base);
  });

  it('restart polls until the stack reports the saved values', async () => {
    let polls = 0;
    mockFetch((url) => {
      if (url.endsWith('/settings/restart')) return { success: true };
      polls += 1;
      return { ...base, restart_required: polls < 3 };
    });
    const p = useCellSettingsStore.getState().restart();
    await vi.advanceTimersByTimeAsync(100);
    expect(useCellSettingsStore.getState().restarting).toBe(true);
    await vi.advanceTimersByTimeAsync(3000 * 4);
    expect(await p).toBe(true);
    expect(useCellSettingsStore.getState().restarting).toBe(false);
    expect(polls).toBe(3);
  });
});
