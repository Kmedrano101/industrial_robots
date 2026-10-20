import { useTranslation } from 'react-i18next';
import Card from '../common/Card';
import type { RobotPageController } from './useRobotPage';

const BED_POINT_ORDER = ['p1', 'p2', 'p3', 'p4', 'center'];

export default function BedPointsCard({ c }: { c: RobotPageController }) {
  const { t } = useTranslation();
  const disabled = c.busy !== null;
  return (
    <Card title={t('test.bedPoints')} collapsible>
      {c.bedLimits?.size_mm && (
        <p className="text-[10px] text-muted mb-2">
          {t('test.bedSize')}: {c.bedLimits.size_mm[0].toFixed(0)} × {c.bedLimits.size_mm[1].toFixed(0)} mm
        </p>
      )}
      <div className="space-y-1.5">
        {BED_POINT_ORDER.filter((k) => c.bedPoints[k]).map((k) => (
          <div key={k} className="grid grid-cols-[auto_1fr_auto] gap-2 items-center">
            <span className="text-xs font-semibold w-14">{k.toUpperCase()}</span>
            <span className="text-[10px] text-muted font-mono truncate">
              {(c.bedPoints[k].deg ?? []).map((d) => d.toFixed(0)).join(', ')}°
            </span>
            <button
              onClick={() => c.gotoBedPoint(k)}
              disabled={disabled}
              className={`min-h-[40px] min-w-[56px] rounded-md border px-3 text-xs transition-colors ${
                disabled
                  ? 'border-line text-faint cursor-not-allowed'
                  : 'border-line hover:bg-accent/15'
              }`}
            >
              {t('test.gotoPoint')}
            </button>
          </div>
        ))}
      </div>
    </Card>
  );
}
