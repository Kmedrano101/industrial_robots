import { useTranslation } from 'react-i18next';
import { usePrintStore } from '../../stores/usePrintStore';
import Card from '../common/Card';

/** Human-readable duration. Slicer estimates are seconds. */
function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return h > 0 ? `${h} h ${m} min` : `${m} min`;
}

/**
 * What the slicer produced, shown between slicing and printing.
 *
 * This is the information an operator decides on — is the estimate
 * plausible, is the layer count what I expected, did it pick the material I
 * meant — and it had nowhere to appear: the slice result existed in the
 * store but the UI only used it to enable the Print button.
 */
export default function SliceSummary() {
  const { t } = useTranslation();
  const sliceResult = usePrintStore((s) => s.sliceResult);
  const uploadedFile = usePrintStore((s) => s.uploadedFile);

  if (!sliceResult) return null;

  const rows: { label: string; value: string }[] = [
    { label: t('summary.layers'), value: String(sliceResult.numLayers) },
    { label: t('summary.estimatedTime'), value: formatDuration(sliceResult.estimatedTime) },
    // Backend returns the material id lowercase ("pla"); it is a product
    // name in the UI, so present it as one.
    { label: t('summary.material'), value: sliceResult.material?.toUpperCase() || '—' },
    { label: t('summary.nozzle'), value: `${sliceResult.nozzleDiameter} mm` },
  ];

  return (
    <Card title={t('summary.title')} collapsible>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
        {rows.map((r) => (
          <div key={r.label} className="contents">
            <dt className="text-gray-500">{r.label}</dt>
            <dd className="text-right font-medium text-gray-800 dark:text-gray-200">
              {r.value}
            </dd>
          </div>
        ))}
      </dl>
      {uploadedFile && (
        <p className="mt-2 truncate border-t border-gray-200 dark:border-gray-800 pt-2 text-[11px] text-gray-500">
          {uploadedFile.filename}
        </p>
      )}
    </Card>
  );
}
