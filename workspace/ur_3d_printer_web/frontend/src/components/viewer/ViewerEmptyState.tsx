import { useTranslation } from 'react-i18next';
import { usePrintStore } from '../../stores/usePrintStore';

/**
 * Overlay shown on the Prepare canvas while there is nothing to look at.
 *
 * Two thirds of the screen used to be bare grid with no indication of what
 * to do — the emptiest moment in the app was also the least instructive.
 * An empty state is the cheapest place to teach the workflow, so it names
 * the current step instead of leaving the operator to hunt the side panel.
 *
 * `pointer-events-none` so it never blocks orbiting the (empty) scene.
 */
export default function ViewerEmptyState() {
  const { t } = useTranslation();
  const uploadedFile = usePrintStore((s) => s.uploadedFile);
  const sliceResult = usePrintStore((s) => s.sliceResult);

  // Once a slice exists the toolpath fills the view and needs no prompt.
  if (sliceResult) return null;

  const step = uploadedFile ? 'slice' : 'import';

  return (
    <div className="pointer-events-none absolute inset-0 z-[5] flex items-center justify-center p-6">
      <div className="max-w-xs text-center">
        <svg
          className="mx-auto mb-3 h-10 w-10 text-gray-400 dark:text-gray-600"
          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}
          aria-hidden="true"
        >
          {step === 'import' ? (
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z" />
          ) : (
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M6 6.878V6a2.25 2.25 0 012.25-2.25h7.5A2.25 2.25 0 0118 6v.878m-12 0c.235-.083.487-.128.75-.128h10.5c.263 0 .515.045.75.128m-12 0A2.25 2.25 0 004.5 9v.878m13.5-3A2.25 2.25 0 0119.5 9v.878m0 0a2.246 2.246 0 00-.75-.128H5.25c-.263 0-.515.045-.75.128m15 0A2.25 2.25 0 0121 12v6a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 18v-6c0-.98.626-1.813 1.5-2.122" />
          )}
        </svg>
        <p className="text-sm font-medium text-gray-600 dark:text-gray-300">
          {t(`viewer.empty.${step}Title`)}
        </p>
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-500">
          {t(`viewer.empty.${step}Hint`)}
        </p>
      </div>
    </div>
  );
}
