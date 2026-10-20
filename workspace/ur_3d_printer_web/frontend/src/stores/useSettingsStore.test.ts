import { describe, expect, it } from 'vitest';
import { migrateSettings, viewModeForPage } from './useSettingsStore';

describe('migrateSettings', () => {
  it('v1 printer page + live view becomes the monitor page', () => {
    const out = migrateSettings({ page: 'printer', viewMode: 'live', theme: 'dark' }, 1);
    expect(out.page).toBe('monitor');
    expect('viewMode' in out).toBe(false);
    expect(out.theme).toBe('dark');
  });

  it('v1 printer page + prepare view becomes the prepare page', () => {
    expect(migrateSettings({ page: 'printer', viewMode: 'prepare' }, 1).page).toBe('prepare');
  });

  it('v1 robot page is kept', () => {
    expect(migrateSettings({ page: 'robot', viewMode: 'live' }, 1).page).toBe('robot');
  });

  it('v0 test view maps to the robot page', () => {
    expect(migrateSettings({ viewMode: 'test' }, 0).page).toBe('robot');
  });

  it('an empty persisted state defaults to prepare', () => {
    expect(migrateSettings({}, 1).page).toBe('prepare');
  });
});

describe('viewModeForPage', () => {
  it('only the monitor page uses the live (metre-scale) viewer', () => {
    expect(viewModeForPage('monitor')).toBe('live');
    expect(viewModeForPage('prepare')).toBe('prepare');
    expect(viewModeForPage('robot')).toBe('prepare');
  });
});
