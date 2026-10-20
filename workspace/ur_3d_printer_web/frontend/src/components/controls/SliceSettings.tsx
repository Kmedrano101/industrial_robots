import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { usePrintStore } from '../../stores/usePrintStore';
import { api } from '../../lib/api';
import {
  DEFAULT_SLICE_SETTINGS,
  INFILL_PATTERNS,
  MATERIALS,
  type InfillPattern,
  type MaterialType,
} from '../../lib/constants';
import type { ToolpathLayer } from '../../types/ros';
import Card from '../common/Card';
import Button from '../common/Button';
import Field, { Input, Select, Segmented } from '../common/Field';
import ProfilePicker from './ProfilePicker';

interface SliceSettings {
  slicer_mode: 'planar' | 'multiaxis';
  layer_height: number;
  nozzle_diameter: number;
  print_speed: number;
  travel_speed: number;
  scale: number;
  max_tilt: number;
  material: MaterialType;
  infill_pattern: InfillPattern;
  infill_density: number;
  infill_angle_base: number;
  infill_angle_increment: number;
}

export default function SliceSettingsPanel() {
  const { t, i18n } = useTranslation();
  const { uploadedFile, isSlicing, setIsSlicing, setSliceResult } = usePrintStore();
  const [settings, setSettings] = useState<SliceSettings>({ ...DEFAULT_SLICE_SETTINGS, material: 'pla' });
  const [error, setError] = useState<string | null>(null);
  const [showInfillAdvanced, setShowInfillAdvanced] = useState(false);

  const patch = (p: Partial<SliceSettings>) => setSettings((s) => ({ ...s, ...p }));

  const handleSlice = async () => {
    if (!uploadedFile) return;
    setIsSlicing(true);
    setError(null);

    try {
      const res = await api.post<{
        gcode_filepath: string;
        num_layers: number;
        estimated_time: number;
        layers: ToolpathLayer[];
      }>('/slice', {
        stl_filepath: uploadedFile.filepath,
        ...settings,
      });

      setSliceResult({
        gcodeFilepath: res.gcode_filepath,
        numLayers: res.num_layers,
        estimatedTime: res.estimated_time,
        layers: res.layers,
        nozzleDiameter: settings.nozzle_diameter,
        material: settings.material,
        slicerMode: settings.slicer_mode,
        layerHeight: settings.layer_height,
        infillPattern: settings.infill_pattern,
        infillDensity: settings.infill_density,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Slice failed');
    } finally {
      setIsSlicing(false);
    }
  };

  if (!uploadedFile) return null;

  const minLayer = settings.nozzle_diameter * 0.25;
  const maxLayer = settings.nozzle_diameter * 0.75;
  const layerTooHigh = settings.layer_height > maxLayer;

  return (
    <Card title={t('slice.title')}>
      <div className="space-y-3">
        <ProfilePicker
          current={settings}
          onApply={(p) => setSettings((s) => ({ ...s, ...p } as SliceSettings))}
        />
        <Segmented<'planar' | 'multiaxis'>
          value={settings.slicer_mode}
          onChange={(slicer_mode) => patch({ slicer_mode })}
          className="w-full"
          stretch
          size="sm"
          aria-label={t('slice.mode')}
          options={[
            { value: 'planar', label: t('slice.planar') },
            { value: 'multiaxis', label: t('slice.multiaxis') },
          ]}
        />

        <div className="grid grid-cols-2 gap-3">
          <Field label={t('slice.material')} className="col-span-2">
            {(id) => (
              <div className="flex items-center gap-2">
                <span
                  className="h-4 w-4 shrink-0 rounded-full border border-line"
                  style={{ backgroundColor: MATERIALS[settings.material].visual.color }}
                  aria-hidden="true"
                />
                <Select id={id} value={settings.material} onChange={(e) => patch({ material: e.target.value as MaterialType })}>
                  {(Object.keys(MATERIALS) as MaterialType[]).map((key) => (
                    <option key={key} value={key}>
                      {i18n.language.startsWith('es') ? MATERIALS[key].label_es : MATERIALS[key].label_en}
                    </option>
                  ))}
                </Select>
              </div>
            )}
          </Field>

          <Field label={t('slice.nozzleDiameter')} hint="mm">
            {(id) => (
              <Input
                id={id}
                type="number"
                step="0.1"
                min="0.1"
                value={settings.nozzle_diameter}
                onChange={(e) => {
                  const nozzle = parseFloat(e.target.value) || 0.4;
                  patch({
                    nozzle_diameter: nozzle,
                    layer_height: Math.min(settings.layer_height, parseFloat((nozzle * 0.75).toFixed(2))),
                  });
                }}
              />
            )}
          </Field>

          <Field
            label={t('slice.layerHeight')}
            hint={`${minLayer.toFixed(2)}–${maxLayer.toFixed(2)} mm`}
            help={layerTooHigh ? t('slice.layerWarning') : undefined}
            warn={layerTooHigh}
          >
            {(id) => (
              <Input
                id={id}
                type="number"
                step="0.05"
                min={parseFloat((settings.nozzle_diameter * 0.1).toFixed(2))}
                max={parseFloat(maxLayer.toFixed(2))}
                value={settings.layer_height}
                onChange={(e) => patch({ layer_height: parseFloat(e.target.value) || 0.2 })}
              />
            )}
          </Field>

          <Field label={t('slice.printSpeed')} hint="mm/min">
            {(id) => (
              <Input
                id={id}
                type="number"
                step="100"
                min="100"
                value={settings.print_speed}
                onChange={(e) => patch({ print_speed: parseInt(e.target.value) || 3000 })}
              />
            )}
          </Field>

          <Field label={t('slice.scale')} hint="×">
            {(id) => (
              <Input
                id={id}
                type="number"
                step="0.1"
                min="0.1"
                value={settings.scale}
                onChange={(e) => patch({ scale: parseFloat(e.target.value) || 1.0 })}
              />
            )}
          </Field>

          {settings.slicer_mode === 'multiaxis' && (
            <Field label={t('slice.maxTilt')} hint="°">
              {(id) => (
                <Input
                  id={id}
                  type="number"
                  step="5"
                  min="0"
                  max="90"
                  value={settings.max_tilt}
                  onChange={(e) => patch({ max_tilt: parseFloat(e.target.value) || 30 })}
                />
              )}
            </Field>
          )}

          <Field label={t('slice.infillPattern')}>
            {(id) => (
              <Select id={id} value={settings.infill_pattern} onChange={(e) => patch({ infill_pattern: e.target.value as InfillPattern })}>
                {INFILL_PATTERNS.map((p) => (
                  <option key={p} value={p}>
                    {t(`slice.infillPatterns.${p}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>

          {settings.infill_pattern !== 'none' && (
            <Field label={t('slice.infillDensity')} hint={`${Math.round(settings.infill_density * 100)}%`}>
              {(id) => (
                <input
                  id={id}
                  type="range"
                  min="5"
                  max="100"
                  step="5"
                  value={Math.round(settings.infill_density * 100)}
                  onChange={(e) => patch({ infill_density: parseInt(e.target.value) / 100 })}
                  className="mt-2.5 block w-full accent-[rgb(var(--c-accent))]"
                />
              )}
            </Field>
          )}
        </div>

        {settings.infill_pattern !== 'none' && (
          <div className="space-y-2">
            <button
              type="button"
              onClick={() => setShowInfillAdvanced((v) => !v)}
              aria-expanded={showInfillAdvanced}
              className="inline-flex min-h-[32px] items-center gap-1 text-xs text-muted hover:text-ink"
            >
              <svg className={`h-3.5 w-3.5 transition-transform ${showInfillAdvanced ? 'rotate-90' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
              {t('slice.infillAdvanced')}
            </button>
            {showInfillAdvanced && (
              <div className="grid grid-cols-2 gap-3">
                <Field label={t('slice.infillAngle')} hint="°">
                  {(id) => (
                    <Input
                      id={id}
                      type="number"
                      step="5"
                      value={settings.infill_angle_base}
                      onChange={(e) => patch({ infill_angle_base: parseFloat(e.target.value) || 0 })}
                    />
                  )}
                </Field>
                <Field label={t('slice.infillAngleStep')} hint="°">
                  {(id) => (
                    <Input
                      id={id}
                      type="number"
                      step="5"
                      value={settings.infill_angle_increment}
                      onChange={(e) => patch({ infill_angle_increment: parseFloat(e.target.value) || 0 })}
                    />
                  )}
                </Field>
              </div>
            )}
          </div>
        )}

        <Button onClick={handleSlice} disabled={isSlicing} className="w-full">
          {isSlicing ? t('controls.slicing') : t('controls.slice')}
        </Button>

        {error && <p className="text-sm text-danger">{t('errors.sliceFailed', { message: error })}</p>}
      </div>
    </Card>
  );
}
