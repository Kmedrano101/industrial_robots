import { useTranslation } from 'react-i18next';
import Card from '../common/Card';
import Button from '../common/Button';
import type { RobotPageController } from './useRobotPage';

export default function ControlCommandsCard({ c }: { c: RobotPageController }) {
  const { t } = useTranslation();
  const offline = !c.connected || c.busy !== null;
  return (
    <Card title={t('test.controlCommands')} collapsible>
      <div className="grid grid-cols-2 gap-2">
        <Button onClick={() => c.runCommand('/robot/power_on', 'power_on')} disabled={offline} variant="primary">
          {t('test.powerOn')}
        </Button>
        <Button onClick={() => c.runCommand('/robot/brake_release', 'brake_release')} disabled={offline} variant="primary">
          {t('test.brakeRelease')}
        </Button>
        <Button onClick={() => c.runCommand('/robot/play', 'play')} disabled={offline} variant="primary">
          {t('test.play')}
        </Button>
        <Button onClick={() => c.runCommand('/robot/stop', 'stop')} disabled={c.busy !== null} variant="danger">
          {t('test.stop')}
        </Button>
        <Button
          onClick={() => c.runCommand('/robot/power_off', 'power_off')}
          disabled={offline}
          variant="secondary"
          className="col-span-2"
        >
          {t('test.powerOff')}
        </Button>
      </div>
    </Card>
  );
}
