import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import Card from '../common/Card';
import Button from '../common/Button';
import Badge from '../common/Badge';
import Field, { Input, Select } from '../common/Field';
import { useCellSettingsStore } from '../../stores/useCellSettingsStore';
import { useRobotStore } from '../../stores/useRobotStore';
import { usePrintStore } from '../../stores/usePrintStore';
import { PrintStateEnum } from '../../types/ros';
import {
  BED_POINT_NAMES, DRIVERS, SERIAL_BAUDS, type ExtruderSettings, type SettingsGroup,
} from '../../types/settings';
import { useGroupDraft } from './useGroupDraft';
import { degToRad, mToMm, mmToM, parseNumber, radToDeg, round, withIndex } from './units';

const JOINT_LABELS = ['Base', 'Shoulder', 'Elbow', 'Wrist 1', 'Wrist 2', 'Wrist 3'];
const AXES = ['X', 'Y', 'Z'];
const RPY = ['R', 'P', 'Y'];

// ── shared pieces ──────────────────────────────────────────────────────────

/** Number input that edits a value kept in SI while showing display units. */
function NumberField({
  label, hint, value, onChange, toDisplay = (v) => v, fromDisplay = (v) => v, step, min, max, help, disabled,
}: {
  label: string;
  hint?: string;
  value: number;
  onChange: (v: number) => void;
  toDisplay?: (v: number) => number;
  fromDisplay?: (v: number) => number;
  step?: number;
  min?: number;
  max?: number;
  help?: string;
  disabled?: boolean;
}) {
  return (
    <Field label={label} hint={hint} help={help}>
      {(id) => (
        <Input
          id={id}
          type="number"
          inputMode="decimal"
          value={toDisplay(value)}
          step={step}
          min={min}
          max={max}
          disabled={disabled}
          onChange={(e) => {
            const v = parseNumber(e.target.value);
            if (v !== null) onChange(fromDisplay(v));
          }}
        />
      )}
    </Field>
  );
}

/** Three-component vector (position in mm or rotation in degrees). */
function VecFields({ label, labels, value, onChange, mode }: {
  label: string;
  labels: string[];
  value: number[];
  onChange: (v: number[]) => void;
  mode: 'mm' | 'deg';
}) {
  const toDisplay = mode === 'mm' ? mToMm : radToDeg;
  const fromDisplay = mode === 'mm' ? mmToM : degToRad;
  return (
    <div className="grid grid-cols-3 gap-2">
      {labels.map((axis, i) => (
        <NumberField
          key={axis}
          label={`${label} ${axis}`}
          hint={mode}
          value={value[i] ?? 0}
          onChange={(v) => onChange(withIndex(value, i, v))}
          toDisplay={toDisplay}
          fromDisplay={fromDisplay}
          step={mode === 'mm' ? 0.1 : 0.1}
        />
      ))}
    </div>
  );
}

function JointsRow({ joints }: { joints: number[] }) {
  return (
    <span className="font-mono text-xs text-muted">
      {joints.map((j) => radToDeg(j).toFixed(1).padStart(7)).join('  ')}°
    </span>
  );
}

/** What the action row needs from a group draft, whichever group it is. */
interface DraftActions {
  dirty: boolean;
  saving: boolean;
  isDefault: boolean;
  discard: () => void;
  save: () => Promise<boolean>;
  reset: () => Promise<boolean>;
}

/** Save / discard / restore-defaults row shared by every card. */
function GroupActions({ group, d }: { group: SettingsGroup; d: DraftActions }) {
  const { t } = useTranslation();
  return (
    <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-3">
      <Button size="sm" onClick={() => void d.save()} disabled={!d.dirty || d.saving}
        disabledReason={t('settings.cell.nothingToSave')}>
        {d.saving ? t('settings.cell.saving') : t('settings.cell.save')}
      </Button>
      <Button size="sm" variant="ghost" onClick={d.discard} disabled={!d.dirty}>
        {t('settings.cell.discard')}
      </Button>
      <Button size="sm" variant="ghost" onClick={() => void d.reset()} disabled={d.isDefault || d.saving}
        disabledReason={t('settings.cell.alreadyDefault')} aria-label={`${t('settings.cell.restoreDefaults')} ${group}`}>
        {t('settings.cell.restoreDefaults')}
      </Button>
      {d.dirty && <span className="text-xs text-warn">{t('settings.cell.unsaved')}</span>}
    </div>
  );
}

function CardBadge({ d }: { d: { awaitingRestart: boolean; isDefault: boolean } }) {
  const { t } = useTranslation();
  if (d.awaitingRestart) return <Badge severity="warn" dot>{t('settings.cell.awaitingRestart')}</Badge>;
  if (d.isDefault) return <Badge severity="neutral">{t('settings.cell.factory')}</Badge>;
  return null;
}

// ── restart banner ─────────────────────────────────────────────────────────

export function RestartBanner() {
  const { t } = useTranslation();
  const doc = useCellSettingsStore((s) => s.doc);
  const restarting = useCellSettingsStore((s) => s.restarting);
  const restart = useCellSettingsStore((s) => s.restart);
  const printState = usePrintStore((s) => s.printState.state);
  const [confirm, setConfirm] = useState(false);
  if (!doc) return null;

  if (restarting) {
    return (
      <div role="status" className="flex items-center gap-3 rounded-xl border border-line bg-surface p-4 text-sm">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        {t('settings.cell.restarting')}
      </div>
    );
  }
  if (doc.restart_required === null) {
    return (
      <p className="text-xs text-muted">{t('settings.cell.restartUnknown')}</p>
    );
  }
  if (!doc.restart_required) return null;

  const printing = printState !== PrintStateEnum.IDLE;
  return (
    <div role="alert" className="rounded-xl border border-warn/40 bg-warn/10 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold">{t('settings.cell.restartRequired')}</div>
          <div className="mt-1 text-xs text-muted">{t('settings.cell.restartHint')}</div>
          <div className="mt-1 font-mono text-[11px] text-muted">{(doc.pending ?? []).join(' · ')}</div>
        </div>
        {!confirm ? (
          <Button size="sm" variant="outline" onClick={() => setConfirm(true)} disabled={printing}
            disabledReason={t('settings.cell.restartWhilePrinting')}>
            {t('settings.cell.restartButton')}
          </Button>
        ) : (
          <div className="flex items-center gap-2">
            <span className="text-xs">{t('settings.cell.restartConfirm')}</span>
            <Button size="sm" variant="danger" onClick={() => { setConfirm(false); void restart(); }}>
              {t('settings.cell.restartYes')}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setConfirm(false)}>{t('settings.cell.cancel')}</Button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── cards ──────────────────────────────────────────────────────────────────

export function ExtruderSettingsCard() {
  const { t } = useTranslation();
  const d = useGroupDraft('extruder');
  const profiles = useCellSettingsStore((s) => s.doc?.extruder_profiles ?? []);
  const info = usePrintStore((s) => s.extruderInfo);
  if (!d.draft) return null;
  const serial = d.draft.driver === 'gcode_serial' || d.draft.driver === '';
  return (
    <Card title={t('settings.cell.extruder')} action={<CardBadge d={d} />}>
      {info && (
        <p className="mb-3 text-xs text-muted">
          {t('settings.cell.mounted')}: <span className="text-ink">{info.name}</span> · {info.kind} · {info.driver}
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t('settings.cell.profile')} className="sm:col-span-2">
          {(id) => (
            <Select id={id} value={d.draft!.profile} onChange={(e) => d.update({ profile: e.target.value })}>
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>{p.name} ({p.kind})</option>
              ))}
              {!profiles.some((p) => p.id === d.draft!.profile) && (
                <option value={d.draft!.profile}>{d.draft!.profile}</option>
              )}
            </Select>
          )}
        </Field>
        <Field label={t('settings.cell.driver')} help={t('settings.cell.driverHelp')}>
          {(id) => (
            <Select id={id} value={d.draft!.driver} onChange={(e) => d.update({ driver: e.target.value as ExtruderSettings['driver'] })}>
              {DRIVERS.map((v) => (
                <option key={v} value={v}>{v === '' ? t('settings.cell.driverFromProfile') : v}</option>
              ))}
            </Select>
          )}
        </Field>
        <Field label={t('settings.cell.serialBaud')}>
          {(id) => (
            <Select id={id} value={d.draft!.serial_baud} disabled={!serial}
              onChange={(e) => d.update({ serial_baud: Number(e.target.value) })}>
              {SERIAL_BAUDS.map((b) => (
                <option key={b} value={b}>{b === 0 ? t('settings.cell.fromProfile') : b}</option>
              ))}
            </Select>
          )}
        </Field>
        <Field label={t('settings.cell.serialPort')} hint="/dev/…" help={t('settings.cell.serialPortHelp')} className="sm:col-span-2">
          {(id) => (
            <Input id={id} value={d.draft!.serial_port} placeholder="/dev/ttyACM0" disabled={!serial}
              onChange={(e) => d.update({ serial_port: e.target.value })} />
          )}
        </Field>
      </div>
      <GroupActions group="extruder" d={d} />
    </Card>
  );
}

export function BedSettingsCard() {
  const { t } = useTranslation();
  const d = useGroupDraft('bed');
  if (!d.draft) return null;
  const b = d.draft;
  return (
    <Card title={t('settings.cell.bed')} action={<CardBadge d={d} />}>
      <p className="mb-3 text-xs text-muted">{t('settings.cell.bedHelp')}</p>
      <div className="space-y-3">
        <VecFields label={t('settings.cell.origin')} labels={AXES} value={b.print_origin_xyz} mode="mm"
          onChange={(v) => d.update({ print_origin_xyz: v })} />
        <VecFields label={t('settings.cell.originRot')} labels={RPY} value={b.print_origin_rpy} mode="deg"
          onChange={(v) => d.update({ print_origin_rpy: v })} />
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <NumberField label={t('settings.cell.tiltX')} hint="deg" value={b.bed_tilt_rx} step={0.01}
            toDisplay={radToDeg} fromDisplay={degToRad} onChange={(v) => d.update({ bed_tilt_rx: v })} />
          <NumberField label={t('settings.cell.tiltY')} hint="deg" value={b.bed_tilt_ry} step={0.01}
            toDisplay={radToDeg} fromDisplay={degToRad} onChange={(v) => d.update({ bed_tilt_ry: v })} />
          <NumberField label={t('settings.cell.bedWidth')} hint="mm" value={b.size_mm[0] ?? 0} step={1} min={50} max={3000}
            onChange={(v) => d.update({ size_mm: withIndex(b.size_mm, 0, round(v, 1)) })} />
          <NumberField label={t('settings.cell.bedDepth')} hint="mm" value={b.size_mm[1] ?? 0} step={1} min={50} max={3000}
            onChange={(v) => d.update({ size_mm: withIndex(b.size_mm, 1, round(v, 1)) })} />
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Field label={t('settings.cell.zHop')}>
            {(id) => (
              <Select id={id} value={b.z_hop_enabled ? 'on' : 'off'}
                onChange={(e) => d.update({ z_hop_enabled: e.target.value === 'on' })}>
                <option value="on">{t('settings.cell.on')}</option>
                <option value="off">{t('settings.cell.off')}</option>
              </Select>
            )}
          </Field>
          <NumberField label={t('settings.cell.zHopHeight')} hint="mm" value={b.z_hop_height} step={0.5} min={0} max={50}
            toDisplay={mToMm} fromDisplay={mmToM} disabled={!b.z_hop_enabled} onChange={(v) => d.update({ z_hop_height: v })} />
        </div>
      </div>
      <GroupActions group="bed" d={d} />
    </Card>
  );
}

export function RobotSettingsCard() {
  const { t } = useTranslation();
  const d = useGroupDraft('robot');
  const capture = useCellSettingsStore((s) => s.capture);
  const saving = useCellSettingsStore((s) => s.saving);
  const robotConnected = useRobotStore((s) => s.robotConnected);
  if (!d.draft) return null;
  const r = d.draft;
  const captureReason = robotConnected ? undefined : t('settings.cell.captureNeedsRobot');
  return (
    <Card title={t('settings.cell.robot')} action={<CardBadge d={d} />}>
      <div className="space-y-4">
        <div>
          <div className="mb-1 flex items-center justify-between gap-2">
            <span className="text-xs text-muted">{t('settings.cell.homeJoints')}</span>
            <Button size="sm" variant="outline" disabled={!robotConnected || saving} disabledReason={captureReason}
              onClick={() => void capture('robot.home_joints')}>
              {t('settings.cell.capture')}
            </Button>
          </div>
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
            {JOINT_LABELS.map((label, i) => (
              <NumberField key={label} label={label} hint="deg" value={r.home_joints[i] ?? 0} step={0.1}
                toDisplay={radToDeg} fromDisplay={degToRad}
                onChange={(v) => d.update({ home_joints: withIndex(r.home_joints, i, v) })} />
            ))}
          </div>
        </div>

        <div>
          <span className="mb-1 block text-xs text-muted">{t('settings.cell.toolOffset')}</span>
          <p className="mb-2 text-[11px] text-faint">{t('settings.cell.toolOffsetHelp')}</p>
          <div className="space-y-2">
            <VecFields label={t('settings.cell.offset')} labels={AXES} value={r.tool_offset_xyz} mode="mm"
              onChange={(v) => d.update({ tool_offset_xyz: v })} />
            <VecFields label={t('settings.cell.offsetRot')} labels={RPY} value={r.tool_offset_rpy} mode="deg"
              onChange={(v) => d.update({ tool_offset_rpy: v })} />
          </div>
        </div>

        <div>
          <span className="mb-1 block text-xs text-muted">{t('settings.cell.bedPoints')}</span>
          <p className="mb-2 text-[11px] text-faint">{t('settings.cell.bedPointsHelp')}</p>
          <table className="w-full text-sm">
            <tbody>
              {BED_POINT_NAMES.map((name) => {
                const joints = r.bed_points[name];
                return (
                  <tr key={name} className="border-t border-line">
                    <td className="py-1.5 pr-3 font-medium uppercase">{name}</td>
                    <td className="py-1.5 pr-3">
                      {joints ? <JointsRow joints={joints} /> : <span className="text-xs text-faint">{t('settings.cell.notSet')}</span>}
                    </td>
                    <td className="py-1.5 text-right">
                      <Button size="sm" variant="ghost" disabled={!robotConnected || saving} disabledReason={captureReason}
                        onClick={() => void capture(`robot.bed_points.${name}`)} aria-label={`${t('settings.cell.capture')} ${name}`}>
                        {t('settings.cell.capture')}
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      <GroupActions group="robot" d={d} />
    </Card>
  );
}

export function MotionSettingsCard() {
  const { t } = useTranslation();
  const d = useGroupDraft('motion');
  if (!d.draft) return null;
  const m = d.draft;
  return (
    <Card title={t('settings.cell.motion')} action={<CardBadge d={d} />}>
      <p className="mb-3 text-xs text-muted">{t('settings.cell.motionHelp')}</p>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <NumberField label={t('settings.cell.printSpeed')} hint="mm/s" value={m.max_print_velocity} step={1} min={1} max={500}
          toDisplay={mToMm} fromDisplay={mmToM} onChange={(v) => d.update({ max_print_velocity: v })} />
        <NumberField label={t('settings.cell.travelSpeed')} hint="mm/s" value={m.max_travel_velocity} step={5} min={1} max={1000}
          toDisplay={mToMm} fromDisplay={mmToM} onChange={(v) => d.update({ max_travel_velocity: v })} />
        <NumberField label={t('settings.cell.acceleration')} hint="mm/s²" value={m.max_acceleration} step={10} min={10} max={5000}
          toDisplay={mToMm} fromDisplay={mmToM} onChange={(v) => d.update({ max_acceleration: v })} />
        <NumberField label={t('settings.cell.blendRadius')} hint="mm" value={m.corner_blend_radius} step={0.5} min={0} max={20}
          toDisplay={mToMm} fromDisplay={mmToM} onChange={(v) => d.update({ corner_blend_radius: v })} />
        <NumberField label={t('settings.cell.singularityScale')} hint="%" value={m.singularity_velocity_scale} step={5} min={5} max={100}
          toDisplay={(v) => round(v * 100, 0)} fromDisplay={(v) => v / 100}
          onChange={(v) => d.update({ singularity_velocity_scale: v })} />
      </div>
      <GroupActions group="motion" d={d} />
    </Card>
  );
}

export function SettingsHistoryCard() {
  const { t } = useTranslation();
  const history = useCellSettingsStore((s) => s.doc?.history ?? []);
  if (history.length === 0) return null;
  return (
    <Card title={t('settings.cell.history')} collapsible defaultCollapsed>
      <ul className="space-y-1 text-xs">
        {history.map((h) => (
          <li key={h.at} className="flex flex-wrap gap-x-3 border-b border-line py-1 last:border-b-0">
            <span className="font-mono text-faint">{new Date(h.at * 1000).toLocaleString()}</span>
            <span className="text-muted">{h.source}</span>
            <span className="font-mono text-ink">{h.changed.join(', ')}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
