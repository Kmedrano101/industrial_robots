import { useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useProfilesStore, type ProfileSettings } from '../../stores/useProfilesStore';
import Field, { Select } from '../common/Field';
import Button from '../common/Button';

interface ProfilePickerProps {
  /** The slicer form's current values, compared against the profiles to
   *  tell which one (if any) is in effect. */
  current: ProfileSettings;
  onApply: (settings: ProfileSettings) => void;
}

const KEYS: (keyof ProfileSettings)[] = [
  'slicer_mode', 'material', 'layer_height', 'nozzle_diameter', 'print_speed',
  'travel_speed', 'scale', 'max_tilt', 'infill_pattern', 'infill_density',
  'infill_angle_base', 'infill_angle_increment',
];

function pick(s: ProfileSettings): ProfileSettings {
  const out: ProfileSettings = {};
  for (const k of KEYS) if (s[k] !== undefined) (out as Record<string, unknown>)[k] = s[k];
  return out;
}

function matches(a: ProfileSettings, b: ProfileSettings): boolean {
  return KEYS.every((k) => b[k] === undefined || a[k] === b[k]);
}

/**
 * Named slicer presets, like the material/process profiles of desktop
 * slicers. The selected profile is derived from the form values rather
 * than stored: edit any field and the picker drops to "Custom", so it
 * never claims a profile that is not what will be sliced.
 */
export default function ProfilePicker({ current, onApply }: ProfilePickerProps) {
  const { t } = useTranslation();
  const profiles = useProfilesStore((s) => s.profiles);
  const loaded = useProfilesStore((s) => s.loaded);
  const error = useProfilesStore((s) => s.error);
  const load = useProfilesStore((s) => s.load);
  const save = useProfilesStore((s) => s.save);
  const remove = useProfilesStore((s) => s.remove);

  useEffect(() => {
    if (!loaded) void load();
  }, [loaded, load]);

  const active = useMemo(
    () => profiles.find((p) => matches(current, p.settings)) ?? null,
    [profiles, current],
  );

  const onSelect = (id: string) => {
    const p = profiles.find((x) => x.id === id);
    if (p) onApply(p.settings);
  };

  const onSave = async () => {
    const name = window.prompt(t('profiles.saveName'), active && !active.builtin ? active.name : '');
    if (!name?.trim()) return;
    await save(name.trim(), pick(current), active && !active.builtin ? active.id : undefined);
  };

  const onDelete = async () => {
    if (!active || active.builtin) return;
    if (!window.confirm(t('profiles.confirmDelete', { name: active.name }))) return;
    await remove(active.id);
  };

  return (
    <div className="flex items-end gap-2">
      <Field label={t('profiles.label')} className="flex-1">
        {(id) => (
          <Select id={id} value={active?.id ?? ''} onChange={(e) => onSelect(e.target.value)}>
            <option value="">{t('profiles.custom')}</option>
            {profiles.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}{p.builtin ? ` · ${t('profiles.builtin')}` : ''}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Button
        size="sm"
        variant="outline"
        onClick={onSave}
        title={active && !active.builtin ? t('profiles.update', { name: active.name }) : t('profiles.save')}
        aria-label={t('profiles.save')}
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
          </svg>
        }
      />
      {active && !active.builtin && (
        <Button
          size="sm"
          variant="ghost"
          onClick={onDelete}
          title={t('profiles.delete')}
          aria-label={t('profiles.delete')}
          icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
            </svg>
          }
        />
      )}
      {error && <span className="sr-only">{t('profiles.error')}</span>}
    </div>
  );
}
