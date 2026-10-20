import { useTranslation } from 'react-i18next';
import Card from '../common/Card';
import StatTile from '../common/StatTile';
import SystemStatus from '../status/SystemStatus';
import PrintControlPanel from '../controls/PrintControlPanel';
import PrintProgress from '../status/PrintProgress';
import ExtruderStatus from '../status/ExtruderStatus';
import TemperatureChart from '../status/TemperatureChart';
import EventLog from '../status/EventLog';
import { usePrintStore } from '../../stores/usePrintStore';
import { useRobotStore } from '../../stores/useRobotStore';
import { PrintStateEnum } from '../../types/ros';
import { deriveSystemStatus, printStateSeverity } from '../../lib/status';
import { JOINT_LABELS, rad2deg } from '../robot/robotConstants';

function formatEta(remainingSeconds: number): string {
  if (!Number.isFinite(remainingSeconds) || remainingSeconds <= 0) return '—';
  return new Date(Date.now() + remainingSeconds * 1000).toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Live view: a row of glanceable figures first, then the detail. */
export default function MonitorPanel() {
  const { t } = useTranslation();
  const printState = usePrintStore((s) => s.printState);
  const progress = usePrintStore((s) => s.printProgress);
  const joints = useRobotStore((s) => s.jointStates.positions);
  const backendConnected = useRobotStore((s) => s.connected);
  const robotConnected = useRobotStore((s) => s.robotConnected);
  const safetyMode = useRobotStore((s) => s.safetyMode);
  const robotMode = useRobotStore((s) => s.robotMode);

  // "A job exists" rather than "is printing": progress that vanishes the
  // instant a print finishes takes the result away exactly when it is read.
  const hasJob =
    progress.total_layers > 0 ||
    [
      PrintStateEnum.PRINTING,
      PrintStateEnum.PAUSED,
      PrintStateEnum.TRAVEL_MOVE,
      PrintStateEnum.LAYER_CHANGE,
      PrintStateEnum.COMPLETED,
      PrintStateEnum.CANCELLING,
    ].includes(printState.state);

  const status = deriveSystemStatus({
    backendConnected,
    robotConnected,
    safetyModeName: safetyMode.mode_name,
    robotModeName: robotMode.mode_name,
    printStateName: printState.state_name,
    printState: printState.state,
  });

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        <StatTile
          label={t('monitor.state')}
          value={t(status.labelKey, printState.state_name)}
          severity={status.severity}
          mono={false}
        />
        <StatTile
          label={t('monitor.progress')}
          value={hasJob ? Math.round(progress.overall_progress * 100) : '—'}
          unit={hasJob ? '%' : undefined}
          severity={hasJob ? printStateSeverity(printState.state_name) : undefined}
        />
        <StatTile
          label={t('monitor.layer')}
          value={hasJob ? `${progress.current_layer}/${progress.total_layers}` : '—'}
          sub={hasJob ? `Z ${(progress.current_z_height * 1000).toFixed(1)} mm` : undefined}
        />
        <StatTile label={t('monitor.eta')} value={hasJob ? formatEta(progress.estimated_remaining) : '—'} />
      </div>

      {/* One status card. Previously a "Connection" card and a "Robot state"
         card sat next to each other and could show "Disconnected" in red
         beside "Ready" in green; both now render the same derivation. */}
      <Card title={t('status.title')}>
        <SystemStatus variant="detailed" />
      </Card>

      <PrintControlPanel />

      {/* Progress stays up for a finished/cancelled job too: hiding it the
         instant a print ends removed the summary right when the operator
         wants to read it. */}
      {hasJob && <PrintProgress />}

      <Card title={t('extruder.title')}>
        <ExtruderStatus />
        <div className="mt-3 border-t border-line pt-3">
          <TemperatureChart />
        </div>
      </Card>

      <Card title={t('live.joints')} collapsible>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 font-mono text-xs">
          {JOINT_LABELS.map((name, i) => (
            <div key={name} className="flex justify-between">
              <span className="text-muted">{name}</span>
              <span>{rad2deg(joints[i] ?? 0).toFixed(1)}°</span>
            </div>
          ))}
        </div>
      </Card>

      <EventLog />
    </div>
  );
}
