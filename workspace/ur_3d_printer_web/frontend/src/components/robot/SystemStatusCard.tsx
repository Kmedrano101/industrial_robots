import { useTranslation } from 'react-i18next';
import { SEVERITY_TEXT } from '../../lib/status';
import Card from '../common/Card';
import Button from '../common/Button';
import type { RobotPageController } from './useRobotPage';

export default function SystemStatusCard({ c }: { c: RobotPageController }) {
  const { t } = useTranslation();
  const { system } = c;
  const freshAge = system.jointStatesAgeS;
  const dataFresh = freshAge != null && freshAge < 0.5;

  return (
    <Card title={t('test.systemStatus')} collapsible>
      <div className="space-y-2 text-sm">
        {/* A — External Control program running */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted">{t('test.externalControl')}</span>
          <span className={`font-semibold ${system.programRunning ? SEVERITY_TEXT.ok : SEVERITY_TEXT.neutral}`}>
            {system.programRunning ? t('test.running') : t('test.stopped')}
          </span>
        </div>
        {/* A — joint_states data freshness */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted">{t('test.dataStream')}</span>
          <span className={`font-mono ${dataFresh ? SEVERITY_TEXT.ok : SEVERITY_TEXT.neutral}`}>
            {freshAge == null ? '—' : `${freshAge.toFixed(2)} s`}
          </span>
        </div>
        {/* C — motion control enabled + active controller */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted">{t('test.motionControl')}</span>
          <span className={`font-semibold ${system.motionControlEnabled ? SEVERITY_TEXT.ok : SEVERITY_TEXT.neutral}`}>
            {system.motionControlEnabled ? t('test.enabled') : t('test.disabled')}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted">{t('test.activeController')}</span>
          <span className="text-xs font-mono">{system.activeTrajectoryController}</span>
        </div>
        <Button
          onClick={c.toggleMotionControl}
          disabled={!c.connected || c.busy !== null}
          variant={system.motionControlEnabled ? 'secondary' : 'primary'}
          className="w-full"
        >
          {system.motionControlEnabled ? t('test.disableMotion') : t('test.enableMotion')}
        </Button>

        {/* E — node health */}
        <div className="mt-2 border-t border-line pt-2">
          <span className="text-xs text-muted mb-1 block">{t('test.nodeHealth')}</span>
          <div className="grid grid-cols-1 gap-y-1 text-xs">
            {Object.keys(system.nodes).length === 0 && <span className="text-muted">—</span>}
            {Object.entries(system.nodes).map(([key, n]) => (
              <div key={key} className="flex items-center justify-between">
                <span className="text-muted">{n.label}</span>
                <span className={n.alive ? SEVERITY_TEXT.ok : SEVERITY_TEXT.danger}>
                  {n.alive ? '● ' + t('test.alive') : '○ ' + t('test.down')}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Card>
  );
}
