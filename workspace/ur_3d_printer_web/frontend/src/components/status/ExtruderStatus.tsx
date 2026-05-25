import { useTranslation } from 'react-i18next';
import { usePrintStore } from '../../stores/usePrintStore';
import { ExtruderStateEnum } from '../../types/ros';

const STATE_NAMES: Record<number, string> = {
  [ExtruderStateEnum.OFF]: 'OFF',
  [ExtruderStateEnum.EXTRUDING]: 'EXTRUDING',
  [ExtruderStateEnum.RETRACTING]: 'RETRACTING',
  [ExtruderStateEnum.PRIMING]: 'PRIMING',
};

export default function ExtruderStatus() {
  const { t } = useTranslation();
  const extruder = usePrintStore((s) => s.extruderState);
  const stateName = STATE_NAMES[extruder.state] || 'OFF';

  return (
    <div className="text-sm space-y-1">
      <div className="flex justify-between">
        <span className="text-gray-500 dark:text-gray-400">{t('extruder.title')}</span>
        <span className="font-medium">{t(`extruder.state.${stateName}`)}</span>
      </div>
      <div className="flex justify-between">
        <span className="text-gray-500 dark:text-gray-400">{t('extruder.temperature')}</span>
        <span>{extruder.temperature.toFixed(0)}°C / {extruder.target_temperature.toFixed(0)}°C</span>
      </div>
    </div>
  );
}
