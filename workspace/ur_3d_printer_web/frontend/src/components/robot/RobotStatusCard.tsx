import { useTranslation } from 'react-i18next';
import { useRobotStore } from '../../stores/useRobotStore';
import { SEVERITY_TEXT } from '../../lib/status';
import Card from '../common/Card';
import ModeBadge from './ModeBadge';
import { JOINT_LABELS, rad2deg } from './robotConstants';

export default function RobotStatusCard() {
  const { t } = useTranslation();
  const joints = useRobotStore((s) => s.jointStates.positions);
  const connected = useRobotStore((s) => s.robotConnected);
  const robotMode = useRobotStore((s) => s.robotMode);
  const safetyMode = useRobotStore((s) => s.safetyMode);
  const motionAllowed = useRobotStore((s) => s.motionAllowed);

  return (
    <Card title={t('test.status')} collapsible>
      <div className="grid grid-cols-1 min-[380px]:grid-cols-2 gap-3 text-sm">
        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted">{t('test.robotMode')}</span>
          <ModeBadge mode={robotMode} kind="robot" />
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted">{t('test.safetyMode')}</span>
          <ModeBadge mode={safetyMode} kind="safety" />
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted">{t('test.connection')}</span>
          <span className={`font-semibold ${connected ? SEVERITY_TEXT.ok : SEVERITY_TEXT.neutral}`}>
            {connected ? t('test.connected') : t('test.disconnected')}
          </span>
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted">{t('test.motionAllowed')}</span>
          <span className={`font-semibold ${motionAllowed ? SEVERITY_TEXT.ok : SEVERITY_TEXT.neutral}`}>
            {motionAllowed ? t('test.yes') : t('test.no')}
          </span>
        </div>
      </div>
      <div className="mt-4 border-t border-line pt-3">
        <span className="text-xs text-muted mb-2 block">{t('test.jointAngles')}</span>
        <div className="grid grid-cols-1 min-[380px]:grid-cols-2 gap-x-4 gap-y-1 text-xs font-mono">
          {JOINT_LABELS.map((n, i) => (
            <div key={n} className="flex justify-between">
              <span className="text-muted">{n}</span>
              <span>{rad2deg(joints[i] ?? 0).toFixed(1)}°</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
