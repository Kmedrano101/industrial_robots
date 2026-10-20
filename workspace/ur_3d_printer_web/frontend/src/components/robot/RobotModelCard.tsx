import { useTranslation } from 'react-i18next';
import { useRobotStore } from '../../stores/useRobotStore';
import { useSettingsStore } from '../../stores/useSettingsStore';
import Card from '../common/Card';
import { ROBOT_MODELS } from './robotConstants';

export default function RobotModelCard() {
  const { t } = useTranslation();
  const backendUrType = useRobotStore((s) => s.urType);
  const robotModel = useSettingsStore((s) => s.robotModel);
  const setRobotModel = useSettingsStore((s) => s.setRobotModel);

  return (
    <Card title={t('settings.robotModel')} collapsible>
      <div className="grid grid-cols-3 sm:grid-cols-4 gap-1.5">
        {ROBOT_MODELS.map((m) => (
          <button
            key={m.value}
            onClick={() => setRobotModel(m.value)}
            className={`rounded-lg px-2 py-2 text-sm font-semibold transition-colors ${
              robotModel === m.value
                ? 'bg-accent text-accent-fg'
                : 'bg-surface2 text-ink hover:bg-line'
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>
      {backendUrType && (
        <p className="mt-2 text-[10px] text-muted">
          {t('test.backendUrType')}: <span className="font-mono">{backendUrType}</span>
          {backendUrType.toLowerCase() !== robotModel && (
            <span className="ml-1 text-warn">{t('test.modelMismatch')}</span>
          )}
        </p>
      )}
    </Card>
  );
}
