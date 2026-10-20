import { useTranslation } from 'react-i18next';
import Card from '../common/Card';
import Button from '../common/Button';
import { JOG_DEGREES, JOINT_LABELS, rad2deg } from './robotConstants';
import type { RobotPageController } from './useRobotPage';

export default function ManualJogCard({ c }: { c: RobotPageController }) {
  const { t } = useTranslation();
  const disabled = c.busy !== null;
  const jogClass = disabled
    ? 'border-gray-600 text-gray-600 cursor-not-allowed'
    : 'border-gray-400 dark:border-gray-600 hover:bg-blue-100 dark:hover:bg-blue-900';

  return (
    <Card title={t('test.manualJog')} collapsible>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs font-mono mb-3">
        {JOINT_LABELS.map((name, i) => (
          <div key={name} className="flex justify-between">
            <span className="text-gray-500">{name}</span>
            <span>{rad2deg(c.displayedJoints[i] ?? 0).toFixed(1)}°</span>
          </div>
        ))}
      </div>
      <div className="space-y-2">
        {JOINT_LABELS.map((name, i) => (
          <div key={name} className="grid grid-cols-[minmax(0,1fr)_repeat(4,_auto)] gap-1 sm:gap-1.5 items-center">
            <span className="truncate text-xs text-gray-500">{name}</span>
            {JOG_DEGREES.map((d) => (
              <button
                key={d}
                onClick={() => c.jog(i, d)}
                disabled={disabled}
                className={`px-2 py-1 text-xs font-mono rounded-md border ${jogClass}`}
              >
                {d > 0 ? `+${d}°` : `${d}°`}
              </button>
            ))}
          </div>
        ))}
      </div>
      <Button onClick={c.home} disabled={disabled} variant="primary" className="w-full mt-3">
        {t('test.moveToHome')}
      </Button>
    </Card>
  );
}
