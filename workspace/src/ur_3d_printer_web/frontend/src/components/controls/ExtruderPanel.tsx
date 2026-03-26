import { useTranslation } from 'react-i18next';
import { api } from '../../lib/api';
import Card from '../common/Card';
import Button from '../common/Button';
import ExtruderStatus from '../status/ExtruderStatus';

export default function ExtruderPanel() {
  const { t } = useTranslation();

  const handleEnable = () => api.post('/extruder', { enable: true, rate: 0.000005 });
  const handleDisable = () => api.post('/extruder', { enable: false });
  const handleRetract = () => api.post('/extruder', { enable: false, retract: true });
  const handlePrime = () => api.post('/extruder', { enable: false, prime: true });

  return (
    <Card title={t('extruder.title')}>
      <ExtruderStatus />
      <div className="mt-3 grid grid-cols-2 gap-2">
        <Button onClick={handleEnable} size="sm" variant="secondary">
          {t('extruder.enable')}
        </Button>
        <Button onClick={handleDisable} size="sm" variant="secondary">
          {t('extruder.disable')}
        </Button>
        <Button onClick={handleRetract} size="sm" variant="secondary">
          {t('extruder.retract')}
        </Button>
        <Button onClick={handlePrime} size="sm" variant="secondary">
          {t('extruder.prime')}
        </Button>
      </div>
    </Card>
  );
}
