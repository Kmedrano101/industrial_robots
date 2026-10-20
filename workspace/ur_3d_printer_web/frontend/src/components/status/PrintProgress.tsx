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

/** Wall-clock time the print is expected to finish — more actionable than
 *  a remaining-duration alone when deciding whether to wait or come back. */
function formatEta(remainingSeconds: number): string | null {
  if (!Number.isFinite(remainingSeconds) || remainingSeconds <= 0) return null;
  const eta = new Date(Date.now() + remainingSeconds * 1000);
  return eta.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

export default function PrintProgress() {
  const { t } = useTranslation();
  const progress = usePrintStore((s) => s.printProgress);
  const eta = formatEta(progress.estimated_remaining);
  const pct = Math.round(progress.overall_progress * 100);

  const rows: [string, string][] = [
    [t('progress.elapsed'), formatTime(progress.elapsed_time)],
    [t('progress.remaining'), formatTime(progress.estimated_remaining)],
    [t('progress.zHeight'), `${(progress.current_z_height * 1000).toFixed(1)} mm`],
    ...(eta ? [[t('progress.eta'), eta] as [string, string]] : []),
  ];

  return (
    // aria-live so progress is announced as it advances rather than being
    // available only to someone watching the bar.
    <Card title={t('progress.overall')} action={<span className="font-mono text-sm font-semibold">{pct}%</span>}>
      <div role="status" aria-live="polite" className="sr-only">
        {t('progress.layer', { current: progress.current_layer, total: progress.total_layers })} {pct}%
      </div>
      <ProgressBar value={progress.overall_progress} />
      <p className="mt-2 text-xs text-muted">
        {t('progress.layer', { current: progress.current_layer, total: progress.total_layers })}
      </p>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-muted">{k}</dt>
            <dd className="text-right font-mono text-ink">{v}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
