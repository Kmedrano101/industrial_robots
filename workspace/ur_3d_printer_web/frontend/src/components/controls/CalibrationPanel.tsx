import { useTranslation } from 'react-i18next';
import { usePrintStore } from '../../stores/usePrintStore';
import { PrintStateEnum } from '../../types/ros';
import { api } from '../../lib/api';
import Card from '../common/Card';
import Button from '../common/Button';

export default function CalibrationPanel() {
  const { t } = useTranslation();
  const state = usePrintStore((s) => s.printState.state);

  const handleCalibrate = () =>
    api.post('/calibrate', { use_current_pose: true });

  return (
    <Card title={t('controls.calibrate')}>
      <Button
        onClick={handleCalibrate}
        disabled={state !== PrintStateEnum.IDLE}
        variant="secondary"
        className="w-full"
      >
        {t('controls.calibrate')}
      </Button>
    </Card>
  );
}
