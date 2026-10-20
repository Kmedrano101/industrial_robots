import { useTranslation } from 'react-i18next';
import { SEVERITY_TEXT } from '../../lib/status';
import Card from '../common/Card';
import { JOINT_LABELS } from './robotConstants';
import type { RobotPageController } from './useRobotPage';

/** Rehearsed pose vs. real arm: overlay toggle and per-joint deviation. */
export default function CompareCard({ c }: { c: RobotPageController }) {
  const { t } = useTranslation();
  return (
    <Card title={t('compare.title')} collapsible defaultCollapsed>
      {!c.canCompare ? (
        <p className="text-xs text-gray-500">
          {!c.connected ? t('compare.needRobot') : t('compare.needRehearsal')}
        </p>
      ) : (
        <>
          <label className="mb-2 inline-flex items-center gap-2 cursor-pointer select-none text-xs">
            <input
              type="checkbox"
              checked={c.compareSim}
              onChange={(e) => c.setCompareSim(e.target.checked)}
              className="h-4 w-4 rounded border-gray-400"
            />
            {t('compare.overlay')}
          </label>
          <p className="mb-2 text-[11px] text-gray-500">{t('compare.hint')}</p>
          <div className="mb-2 flex items-baseline justify-between border-y border-gray-200 dark:border-gray-800 py-1.5">
            <span className="text-xs text-gray-500">{t('compare.maxDeviation')}</span>
            <span className={`font-mono text-sm font-semibold ${
              c.maxDeviationDeg > 1 ? SEVERITY_TEXT.warn : SEVERITY_TEXT.ok
            }`}>
              {c.maxDeviationDeg.toFixed(2)}°
            </span>
          </div>
          <dl className="grid grid-cols-1 min-[380px]:grid-cols-2 gap-x-4 gap-y-1 text-[11px] font-mono">
            {JOINT_LABELS.map((name, i) => (
              <div key={name} className="flex justify-between">
                <dt className="truncate text-gray-500">{name}</dt>
                <dd>{c.jointDeviationsDeg[i] >= 0 ? '+' : ''}{c.jointDeviationsDeg[i].toFixed(2)}°</dd>
              </div>
            ))}
          </dl>
        </>
      )}
    </Card>
  );
}
