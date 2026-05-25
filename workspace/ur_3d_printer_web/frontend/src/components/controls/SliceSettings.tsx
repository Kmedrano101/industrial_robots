import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { usePrintStore } from '../../stores/usePrintStore';
import { api } from '../../lib/api';
import { DEFAULT_SLICE_SETTINGS, MATERIALS, type MaterialType } from '../../lib/constants';
import type { ToolpathLayer } from '../../types/ros';
import Card from '../common/Card';
import Button from '../common/Button';

interface SliceSettings {
  slicer_mode: 'planar' | 'multiaxis';
  layer_height: number;
  nozzle_diameter: number;
  print_speed: number;
  travel_speed: number;
  scale: number;
  max_tilt: number;
  material: MaterialType;
}

export default function SliceSettingsPanel() {
  const { t, i18n } = useTranslation();
  const { uploadedFile, isSlicing, setIsSlicing, setSliceResult, sliceResult } = usePrintStore();
  const [settings, setSettings] = useState<SliceSettings>({ ...DEFAULT_SLICE_SETTINGS, material: 'pla' });
  const [error, setError] = useState<string | null>(null);

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
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Slice failed');
    } finally {
      setIsSlicing(false);
    }
  };

  if (!uploadedFile) return null;

  return (
    <Card title={t('slice.title')}>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="text-xs text-gray-500 dark:text-gray-400">{t('slice.mode')}</span>
            <select
              value={settings.slicer_mode}
              onChange={(e) => setSettings({ ...settings, slicer_mode: e.target.value as 'planar' | 'multiaxis' })}
              className="mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm px-2 py-1.5"
            >
              <option value="planar">{t('slice.planar')}</option>
              <option value="multiaxis">{t('slice.multiaxis')}</option>
            </select>
          </label>
          <label className="block">
            <span className="text-xs text-gray-500 dark:text-gray-400">{t('slice.material')}</span>
            <div className="mt-1 flex items-center gap-2">
              <span
                className="inline-block w-4 h-4 rounded-full border border-gray-400 dark:border-gray-500 flex-shrink-0"
                style={{ backgroundColor: MATERIALS[settings.material].visual.color }}
              />
              <select
                value={settings.material}
                onChange={(e) => setSettings({ ...settings, material: e.target.value as MaterialType })}
                className="block w-full rounded-md border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm px-2 py-1.5"
              >
                {(Object.keys(MATERIALS) as MaterialType[]).map((key) => (
                  <option key={key} value={key}>
                    {i18n.language === 'es' ? MATERIALS[key].label_es : MATERIALS[key].label_en}
                  </option>
                ))}
              </select>
            </div>
          </label>
          <label className="block">
            <span className="text-xs text-gray-500 dark:text-gray-400">{t('slice.nozzleDiameter')}</span>
            <input
              type="number"
              step="0.1"
              min="0.1"
              value={settings.nozzle_diameter}
              onChange={(e) => {
                const nozzle = parseFloat(e.target.value) || 0.4;
                const maxLayer = nozzle * 0.75;
                setSettings({
                  ...settings,
                  nozzle_diameter: nozzle,
                  layer_height: Math.min(settings.layer_height, parseFloat(maxLayer.toFixed(2))),
                });
              }}
              className="mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm px-2 py-1.5"
            />
          </label>
          <label className="block">
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {t('slice.layerHeight')}
              <span className="text-gray-400 dark:text-gray-500"> ({(settings.nozzle_diameter * 0.25).toFixed(2)}-{(settings.nozzle_diameter * 0.75).toFixed(2)})</span>
            </span>
            <input
              type="number"
              step="0.05"
              min={parseFloat((settings.nozzle_diameter * 0.1).toFixed(2))}
              max={parseFloat((settings.nozzle_diameter * 0.75).toFixed(2))}
              value={settings.layer_height}
              onChange={(e) => setSettings({ ...settings, layer_height: parseFloat(e.target.value) || 0.2 })}
              className="mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm px-2 py-1.5"
            />
            {settings.layer_height > settings.nozzle_diameter * 0.75 && (
              <span className="text-[10px] text-amber-500">{t('slice.layerWarning')}</span>
            )}
          </label>
          <label className="block">
            <span className="text-xs text-gray-500 dark:text-gray-400">{t('slice.printSpeed')}</span>
            <input
              type="number"
              step="100"
              min="100"
              value={settings.print_speed}
              onChange={(e) => setSettings({ ...settings, print_speed: parseInt(e.target.value) || 3000 })}
              className="mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm px-2 py-1.5"
            />
          </label>
          <label className="block">
            <span className="text-xs text-gray-500 dark:text-gray-400">{t('slice.scale')}</span>
            <input
              type="number"
              step="0.1"
              min="0.1"
              value={settings.scale}
              onChange={(e) => setSettings({ ...settings, scale: parseFloat(e.target.value) || 1.0 })}
              className="mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm px-2 py-1.5"
            />
          </label>
          {settings.slicer_mode === 'multiaxis' && (
            <label className="block">
              <span className="text-xs text-gray-500 dark:text-gray-400">{t('slice.maxTilt')}</span>
              <input
                type="number"
                step="5"
                min="0"
                max="90"
                value={settings.max_tilt}
                onChange={(e) => setSettings({ ...settings, max_tilt: parseFloat(e.target.value) || 30 })}
                className="mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm px-2 py-1.5"
              />
            </label>
          )}
        </div>

        <Button onClick={handleSlice} disabled={isSlicing} className="w-full">
          {isSlicing ? t('controls.slicing') : t('controls.slice')}
        </Button>

        {error && <p className="text-sm text-red-500">{t('errors.sliceFailed', { message: error })}</p>}

        {sliceResult && (
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {t('progress.layers', { count: sliceResult.numLayers })} · {t('progress.estimatedTime', { time: `${Math.round(sliceResult.estimatedTime)}s` })}
          </p>
        )}
      </div>
    </Card>
  );
}
