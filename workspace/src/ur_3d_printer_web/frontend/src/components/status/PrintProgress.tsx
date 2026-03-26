import { useTranslation } from 'react-i18next';
import { usePrintStore } from '../../stores/usePrintStore';
import Card from '../common/Card';
import ProgressBar from '../common/ProgressBar';

function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export default function PrintProgress() {
  const { t } = useTranslation();
  const progress = usePrintStore((s) => s.printProgress);

  return (
    <Card title={t('progress.overall')}>
      <ProgressBar value={progress.overall_progress} className="mb-3" />
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <span className="text-gray-500 dark:text-gray-400">{t('progress.layer', { current: progress.current_layer, total: progress.total_layers })}</span>
        </div>
        <div className="text-right">
          <span className="text-gray-500 dark:text-gray-400">{Math.round(progress.overall_progress * 100)}%</span>
        </div>
        <div>
          <span className="text-gray-500 dark:text-gray-400">{t('progress.elapsed')}: </span>
          {formatTime(progress.elapsed_time)}
        </div>
        <div className="text-right">
          <span className="text-gray-500 dark:text-gray-400">{t('progress.remaining')}: </span>
          {formatTime(progress.estimated_remaining)}
        </div>
        <div>
          <span className="text-gray-500 dark:text-gray-400">{t('progress.zHeight')}: </span>
          {(progress.current_z_height * 1000).toFixed(1)} mm
        </div>
      </div>
    </Card>
  );
}
