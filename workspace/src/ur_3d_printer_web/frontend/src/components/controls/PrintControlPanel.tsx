import { useTranslation } from 'react-i18next';
import { usePrintStore } from '../../stores/usePrintStore';
import { PrintStateEnum } from '../../types/ros';
import { api } from '../../lib/api';
import Card from '../common/Card';
import Button from '../common/Button';

export default function PrintControlPanel() {
  const { t } = useTranslation();
  const { printState, sliceResult } = usePrintStore();
  const state = printState.state;

  const canStart = state === PrintStateEnum.IDLE && sliceResult !== null;
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
        <Button onClick={handleStart} disabled={!canStart} className="col-span-2">
          {t('controls.start')}
        </Button>
        <Button onClick={handlePause} disabled={!canPause} variant="secondary">
          {t('controls.pause')}
        </Button>
        <Button onClick={handleResume} disabled={!canResume} variant="secondary">
          {t('controls.resume')}
        </Button>
        <Button onClick={handleCancel} disabled={!canCancel} variant="danger">
          {t('controls.cancel')}
        </Button>
        <Button
          onClick={handleCalibrate}
          disabled={state !== PrintStateEnum.IDLE}
          variant="secondary"
        >
          {t('controls.calibrate')}
        </Button>
      </div>
      {printState.error_message && (
        <p className="mt-2 text-sm text-red-500">{printState.error_message}</p>
      )}
    </Card>
  );
}
