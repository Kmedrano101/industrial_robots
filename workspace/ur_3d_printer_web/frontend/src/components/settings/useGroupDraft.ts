import { useCallback, useEffect, useState } from 'react';
import { useCellSettingsStore } from '../../stores/useCellSettingsStore';
import type { CellSettings, SettingsGroup } from '../../types/settings';
import { sameValue } from './units';

/** Local, editable copy of one settings group.
 *
 *  Edits stay in the browser until Save sends the whole group as a patch;
 *  the draft is re-seeded whenever the server copy changes (after a save,
 *  a reset, a capture, or another device's edit arriving on reload), so
 *  what the form shows is always relative to what the cell really has. */
export function useGroupDraft<G extends SettingsGroup>(group: G) {
  const server = useCellSettingsStore((s) => s.doc?.settings[group]) as CellSettings[G] | undefined;
  const defaults = useCellSettingsStore((s) => s.doc?.defaults[group]) as CellSettings[G] | undefined;
  const pending = useCellSettingsStore((s) => s.doc?.pending);
  const saving = useCellSettingsStore((s) => s.saving);
  const save = useCellSettingsStore((s) => s.save);
  const reset = useCellSettingsStore((s) => s.reset);
  const [draft, setDraft] = useState<CellSettings[G] | undefined>(server);

  useEffect(() => {
    setDraft(server ? (JSON.parse(JSON.stringify(server)) as CellSettings[G]) : undefined);
  }, [server]);

  const update = useCallback((patch: Partial<CellSettings[G]>) => {
    setDraft((d) => (d ? { ...d, ...patch } : d));
  }, []);

  const dirty = draft !== undefined && server !== undefined && !sameValue(draft, server);
  const isDefault = server !== undefined && defaults !== undefined && sameValue(server, defaults);
  // Saved but not yet running: the node names in `pending` map to groups.
  const awaitingRestart = (pending ?? []).some((p) => GROUP_OF_PARAM(p) === group);

  return {
    draft,
    server,
    dirty,
    isDefault,
    awaitingRestart,
    saving,
    update,
    discard: () => setDraft(server ? (JSON.parse(JSON.stringify(server)) as CellSettings[G]) : undefined),
    save: () => (draft ? save({ [group]: draft } as Parameters<typeof save>[0]) : Promise.resolve(false)),
    reset: () => reset(group),
  };
}

const BED_PARAMS = new Set(['print_origin_xyz', 'print_origin_rpy', 'bed_tilt_rx', 'bed_tilt_ry', 'z_hop_enabled', 'z_hop_height']);
const ROBOT_PARAMS = new Set(['home_joints', 'tool_offset_xyz', 'tool_offset_rpy']);

/** `print_node.z_hop_height` → 'bed'; `extruder_controller.driver` → 'extruder'. */
export function GROUP_OF_PARAM(pending: string): SettingsGroup | null {
  const [node, param] = pending.split('.');
  if (node === 'extruder_controller') return 'extruder';
  if (node !== 'print_node') return null;
  if (BED_PARAMS.has(param)) return 'bed';
  if (ROBOT_PARAMS.has(param)) return 'robot';
  return 'motion';
}
