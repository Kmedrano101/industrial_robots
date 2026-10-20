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
 *
 * Laid out as four equal columns with the label under the marker: the
 * Spanish labels ("Previsualizar") do not fit beside the markers in a
 * 400 px panel, and a stepper that truncates its own step names defeats
 * its purpose.
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
    { key: 'import', label: t('workflow.import'), state: hasFile ? 'done' : 'current' },
    { key: 'slice', label: t('workflow.slice'), state: hasSlice ? 'done' : hasFile ? 'current' : 'pending' },
    { key: 'preview', label: t('workflow.preview'), state: hasSlice ? 'done' : 'pending' },
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
    <nav aria-label={t('workflow.title')} className="rounded-xl border border-line bg-surface px-2 py-2.5 shadow-card">
      <ol className="relative grid grid-cols-4">
        {/* Connector track behind the markers; the filled part grows with
           the done steps. */}
        <div className="absolute left-[12.5%] right-[12.5%] top-3 h-px bg-line" aria-hidden="true" />
        {steps.map((step, i) => {
          const busy = step.key === 'slice' && isSlicing;
          const nextDone = steps[i + 1]?.state === 'done' || (step.state === 'done' && steps[i + 1]?.state === 'current');
          return (
            <li key={step.key} className="relative flex min-w-0 flex-col items-center gap-1.5">
              {i < steps.length - 1 && step.state === 'done' && (
                <div
                  className={`absolute left-1/2 top-3 h-px w-full ${nextDone ? 'bg-ok/70' : 'bg-ok/40'}`}
                  aria-hidden="true"
                />
              )}
              <span
                aria-current={step.state === 'current' ? 'step' : undefined}
                className={`relative z-[1] flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-bold ${
                  step.state === 'done'
                    ? 'bg-ok text-white'
                    : step.state === 'current'
                    ? 'bg-accent text-accent-fg ring-4 ring-accent/20'
                    : 'bg-surface2 text-faint ring-2 ring-surface'
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
                className={`max-w-full truncate px-1 text-center text-[11px] leading-tight ${
                  step.state === 'pending' ? 'text-faint' : 'font-medium text-ink'
                }`}
              >
                {step.label}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
