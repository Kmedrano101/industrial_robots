import { useTranslation } from 'react-i18next';
import { usePrintStore } from '../../stores/usePrintStore';
import { useRobotStore } from '../../stores/useRobotStore';

/**
 * The print pipeline, made visible.
 *
 * The steps always existed but were never stated, and the panel hid the
 * ones that were not yet applicable — SliceSettings renders nothing without
 * an uploaded file, so a first-time user saw an upload box followed
 * immediately by print controls, with no hint that slicing sits between
 * them. Showing the whole pipeline (including steps not yet reachable)
 * is what desktop slicers do, and it answers "where am I / what is next"
 * without a manual.
 */

type StepState = 'done' | 'current' | 'pending';

export default function WorkflowSteps() {
  const { t } = useTranslation();
  const uploadedFile = usePrintStore((s) => s.uploadedFile);
  const sliceResult = usePrintStore((s) => s.sliceResult);
  const isSlicing = usePrintStore((s) => s.isSlicing);
  const robotConnected = useRobotStore((s) => s.robotConnected);

  const hasFile = uploadedFile !== null;
  const hasSlice = sliceResult !== null;

  const steps: { key: string; label: string; state: StepState }[] = [
    {
      key: 'import',
      label: t('workflow.import'),
      state: hasFile ? 'done' : 'current',
    },
    {
      key: 'slice',
      label: t('workflow.slice'),
      state: hasSlice ? 'done' : hasFile ? 'current' : 'pending',
    },
    {
      key: 'preview',
      label: t('workflow.preview'),
      state: hasSlice ? 'done' : 'pending',
    },
    {
      key: 'print',
      label: t('workflow.print'),
      // Reaching this step needs a robot as well as a slice; leaving it
      // "current" without one would repeat the old lie that printing is
      // available. PrintControlPanel states the specific reason.
      state: hasSlice && robotConnected ? 'current' : 'pending',
    },
  ];

  return (
    <nav aria-label={t('workflow.title')} className="px-1">
      <ol className="flex items-center gap-1">
        {steps.map((step, i) => {
          const isLast = i === steps.length - 1;
          const busy = step.key === 'slice' && isSlicing;
          return (
            <li key={step.key} className="flex items-center gap-1 min-w-0">
              <div
                className="flex items-center gap-1.5 min-w-0"
                aria-current={step.state === 'current' ? 'step' : undefined}
              >
                <span
                  className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
                    step.state === 'done'
                      ? 'bg-emerald-600 text-white'
                      : step.state === 'current'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-200 dark:bg-gray-800 text-gray-400 dark:text-gray-600'
                  }`}
                >
                  {busy ? (
                    <span className="h-2 w-2 animate-pulse rounded-full bg-white" />
                  ) : step.state === 'done' ? (
                    '✓'
                  ) : (
                    i + 1
                  )}
                </span>
                <span
                  className={`truncate text-[11px] ${
                    step.state === 'pending'
                      ? 'text-gray-400 dark:text-gray-600'
                      : 'font-medium text-gray-700 dark:text-gray-300'
                  }`}
                >
                  {step.label}
                </span>
              </div>
              {!isLast && (
                <span
                  className={`h-px w-3 shrink-0 ${
                    step.state === 'done'
                      ? 'bg-emerald-600/60'
                      : 'bg-gray-300 dark:bg-gray-700'
                  }`}
                  aria-hidden="true"
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
