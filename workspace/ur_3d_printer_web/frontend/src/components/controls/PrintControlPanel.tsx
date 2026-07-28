import { useTranslation } from 'react-i18next';
import { usePrintStore } from '../../stores/usePrintStore';
import { useRobotStore } from '../../stores/useRobotStore';
import { PrintStateEnum } from '../../types/ros';
import { api } from '../../lib/api';
import Card from '../common/Card';
import Button from '../common/Button';

export default function PrintControlPanel() {
  const { t } = useTranslation();
  const { printState, sliceResult } = usePrintStore();
  const robotConnected = useRobotStore((s) => s.robotConnected);
  const state = printState.state;

  // Each gate reports WHY it blocks, so a greyed-out control explains itself
  // instead of being a dead end. Order matters: name the most fundamental
  // missing precondition first. Note "no robot" was not previously checked
  // at all — Start was enabled whenever a slice existed, even with nothing
  // on the other end.
  const startBlockedReason = !robotConnected
    ? t('controls.blocked.noRobot')
    : !sliceResult
    ? t('controls.blocked.notSliced')
    : state !== PrintStateEnum.IDLE
    ? t('controls.blocked.busy')
    : null;

  const calibrateBlockedReason = !robotConnected
    ? t('controls.blocked.noRobot')
    : state !== PrintStateEnum.IDLE
    ? t('controls.blocked.busy')
    : null;

  const canStart = startBlockedReason === null;
  const canPause = state === PrintStateEnum.PRINTING;
  const canResume = state === PrintStateEnum.PAUSED;
  const canCancel = state === PrintStateEnum.PRINTING || state === PrintStateEnum.PAUSED;

  const handleStart = async () => {
    if (!sliceResult) return;
    await api.post('/print/start', { gcode_filepath: sliceResult.gcodeFilepath });
  };

  const handlePause = () => api.post('/print/pause');
  const handleResume = () => api.post('/print/resume');
  const handleCancel = () => api.post('/print/cancel', { retract_and_home: true });
  const handleCalibrate = () => api.post('/calibrate', { use_current_pose: true });

  return (
    <Card>
      <div className="grid grid-cols-2 gap-2">
        <Button
          onClick={handleStart}
          disabled={!canStart}
          disabledReason={startBlockedReason ?? undefined}
          className="col-span-2"
        >
          {t('controls.start')}
        </Button>
        <Button
          onClick={handlePause}
          disabled={!canPause}
          disabledReason={t('controls.blocked.notPrinting')}
          variant="secondary"
        >
          {t('controls.pause')}
        </Button>
        <Button
          onClick={handleResume}
          disabled={!canResume}
          disabledReason={t('controls.blocked.notPaused')}
          variant="secondary"
        >
          {t('controls.resume')}
        </Button>
        <Button
          onClick={handleCancel}
          disabled={!canCancel}
          disabledReason={t('controls.blocked.notPrinting')}
          variant="danger"
        >
          {t('controls.cancel')}
        </Button>
        <Button
          onClick={handleCalibrate}
          disabled={calibrateBlockedReason !== null}
          disabledReason={calibrateBlockedReason ?? undefined}
          variant="secondary"
        >
          {t('controls.calibrate')}
        </Button>
      </div>

      {/* State the reason inline as well: a tooltip is invisible on touch,
         and this panel is used from a tablet beside the machine. */}
      {startBlockedReason && (
        <p className="mt-2 text-xs text-gray-500">
          {t('controls.blocked.prefix')}: {startBlockedReason}
        </p>
      )}
      {printState.error_message && (
        <p className="mt-2 text-sm text-red-600 dark:text-red-400">
          {printState.error_message}
        </p>
      )}
    </Card>
  );
}
