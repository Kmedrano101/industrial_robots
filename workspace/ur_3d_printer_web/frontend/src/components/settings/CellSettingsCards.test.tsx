import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MotionSettingsCard, RestartBanner } from './CellSettingsCards';
import { useCellSettingsStore } from '../../stores/useCellSettingsStore';
import { usePrintStore } from '../../stores/usePrintStore';
import { PrintStateEnum } from '../../types/ros';
import type { SettingsDocument } from '../../types/settings';
import i18n from '../../i18n';

const settings: SettingsDocument['settings'] = {
  version: 1,
  extruder: { profile: 'mahor_v5_m12_pro', driver: 'mock', serial_port: '', serial_baud: 0 },
  bed: { print_origin_xyz: [-0.3, 0, -0.01], print_origin_rpy: [0, 0, 0], bed_tilt_rx: 0, bed_tilt_ry: 0, z_hop_enabled: true, z_hop_height: 0.008, size_mm: [300, 300] },
  robot: { home_joints: [0, -1.57, 1.57, -1.57, -1.57, 0], tool_offset_xyz: [0, 0, 0.105], tool_offset_rpy: [0, 0, 0], bed_points: {} },
  motion: { max_print_velocity: 0.05, max_travel_velocity: 0.15, max_acceleration: 0.5, corner_blend_radius: 0.002, singularity_velocity_scale: 0.3 },
};
const doc = (over: Partial<SettingsDocument> = {}): SettingsDocument => ({
  settings, defaults: settings, extruder_profiles: [], effective: {}, restart_required: false,
  pending: [], restart_requested_at: null, updated_at: null, history: [], ...over,
});

beforeEach(async () => {
  await i18n.changeLanguage('en');
  useCellSettingsStore.setState({ doc: doc(), loading: false, saving: false, restarting: false, error: null });
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe('MotionSettingsCard', () => {
  it('shows SI values in mm/s and sends the edited group in SI on save', async () => {
    const calls: unknown[] = [];
    vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) => {
      calls.push(JSON.parse(String(init?.body)));
      return new Response(JSON.stringify(doc({ pending: ['print_node.max_print_velocity'], restart_required: true })),
        { status: 200, headers: { 'Content-Type': 'application/json' } });
    }));
    render(<MotionSettingsCard />);
    const speed = screen.getByLabelText(/Print speed/) as HTMLInputElement;
    expect(speed.value).toBe('50');
    const save = screen.getByRole('button', { name: 'Save' });
    expect(save).toBeDisabled();
    fireEvent.change(speed, { target: { value: '80' } });
    expect(screen.getByText('Unsaved changes')).toBeInTheDocument();
    fireEvent.click(save);
    await waitFor(() => expect(calls).toHaveLength(1));
    expect(calls[0]).toEqual({ patch: { motion: { ...settings.motion, max_print_velocity: 0.08 } }, source: 'web' });
    await waitFor(() => expect(screen.getByText('Awaiting restart')).toBeInTheDocument());
  });

  it('factory badge when the group equals the defaults', () => {
    render(<MotionSettingsCard />);
    expect(screen.getByText('Factory')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Factory defaults/ })).toBeDisabled();
  });
});

describe('RestartBanner', () => {
  it('is hidden when nothing is pending and explains when ROS is unreachable', () => {
    const { rerender } = render(<RestartBanner />);
    expect(screen.queryByRole('alert')).toBeNull();
    useCellSettingsStore.setState({ doc: doc({ restart_required: null, pending: null }) });
    rerender(<RestartBanner />);
    expect(screen.getByText(/ROS unavailable/)).toBeInTheDocument();
  });

  it('asks for confirmation and refuses while printing', () => {
    useCellSettingsStore.setState({ doc: doc({ restart_required: true, pending: ['print_node.z_hop_height'] }) });
    render(<RestartBanner />);
    expect(screen.getByText('print_node.z_hop_height')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Restart ROS stack' }));
    expect(screen.getByRole('button', { name: 'Yes, restart' })).toBeInTheDocument();
    usePrintStore.setState({ printState: { state: PrintStateEnum.PRINTING, state_name: 'PRINTING', error_message: '' } });
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.getByRole('button', { name: 'Restart ROS stack' })).toBeDisabled();
    usePrintStore.setState({ printState: { state: PrintStateEnum.IDLE, state_name: 'IDLE', error_message: '' } });
  });
});

describe('live apply', () => {
  it('marks the group applied when print_node took the values', () => {
    useCellSettingsStore.setState({ doc: doc({
      settings: { ...settings, motion: { ...settings.motion, max_print_velocity: 0.08 } },
      applied: ['max_print_velocity'],
    }) });
    render(<MotionSettingsCard />);
    expect(screen.getByText('Applied')).toBeInTheDocument();
  });

  it('shows why a save was not applied live', () => {
    useCellSettingsStore.setState({ doc: doc({ apply_error: 'print in progress' }) });
    render(<RestartBanner />);
    expect(screen.getByText(/Not applied live: print in progress/)).toBeInTheDocument();
  });
});
