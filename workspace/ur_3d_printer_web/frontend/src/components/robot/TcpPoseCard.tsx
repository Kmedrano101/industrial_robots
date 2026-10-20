import { useTranslation } from 'react-i18next';
import Card from '../common/Card';
import type { RobotPageController } from './useRobotPage';

export default function TcpPoseCard({ pose }: { pose: RobotPageController['pose'] }) {
  const { t } = useTranslation();
  const deg = (r: number) => ((r * 180) / Math.PI).toFixed(1);
  return (
    <Card title={t('test.tcpPose')} collapsible>
      <p className="text-[10px] text-gray-500 mb-1">{t('test.tcpFrame')}</p>
      <div className="grid grid-cols-2 gap-3 text-xs font-mono">
        <div>
          <span className="text-gray-500">{t('test.position')} (m)</span>
          <div>X&nbsp;&nbsp;{pose.pos[0].toFixed(3)}</div>
          <div>Y&nbsp;&nbsp;{pose.pos[1].toFixed(3)}</div>
          <div>Z&nbsp;&nbsp;{pose.pos[2].toFixed(3)}</div>
        </div>
        <div>
          <span className="text-gray-500">{t('test.orientation')} (°)</span>
          <div>R&nbsp;&nbsp;{deg(pose.rpy[0])}</div>
          <div>P&nbsp;&nbsp;{deg(pose.rpy[1])}</div>
          <div>Y&nbsp;&nbsp;{deg(pose.rpy[2])}</div>
        </div>
      </div>
    </Card>
  );
}
