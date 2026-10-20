import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import JobsPage from './JobsPage';
import i18n from '../../i18n';

const job = (over: Record<string, unknown>) => ({
  id: 'abc', started_at: 1_700_000_000, finished_at: 1_700_003_600, status: 'completed',
  filename: 'cube.stl', gcode_path: '/data/uploads/x.gcode', material: 'pla',
  slicer_mode: 'planar', layer_height: 0.2, nozzle_diameter: 0.4, infill_pattern: 'linear',
  infill_density: 0.2, num_layers: 20, estimated_time: 600, layers_done: 20,
  elapsed_time: 3600, error_message: null, source: 'web', ...over,
});

function mockFetch(jobs: unknown[]) {
  const calls: string[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push(`${init?.method ?? 'GET'} ${url}`);
    return new Response(JSON.stringify({ jobs, current: null, success: true }), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    });
  }));
  return calls;
}

beforeEach(async () => {
  await i18n.changeLanguage('en');
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe('JobsPage', () => {
  it('shows the empty state', async () => {
    mockFetch([]);
    render(<JobsPage />);
    expect(await screen.findByText('No jobs recorded yet.')).toBeInTheDocument();
  });

  it('lists jobs with status badges and marks external ones', async () => {
    mockFetch([job({}), job({ id: 'def', status: 'error', error_message: 'jam', source: 'external', filename: null })]);
    render(<JobsPage />);
    expect(await screen.findByText('cube.stl')).toBeInTheDocument();
    expect(screen.getByText('Completed')).toBeInTheDocument();
    expect(screen.getByText('Error')).toBeInTheDocument();
    expect(screen.getByText('(unnamed)')).toBeInTheDocument();
    expect(screen.getByText('ROS')).toBeInTheDocument();
  });

  it('expands a row to show the slice settings', async () => {
    mockFetch([job({})]);
    render(<JobsPage />);
    fireEvent.click(await screen.findByText('cube.stl'));
    expect(screen.getByText('linear · 20%')).toBeInTheDocument();
    expect(screen.getByText('/data/uploads/x.gcode')).toBeInTheDocument();
  });

  it('deletes a job after confirmation', async () => {
    const calls = mockFetch([job({})]);
    vi.stubGlobal('confirm', () => true);
    render(<JobsPage />);
    fireEvent.click(await screen.findByLabelText('Delete'));
    await waitFor(() => expect(calls).toContain('DELETE /api/jobs/abc'));
  });
});
