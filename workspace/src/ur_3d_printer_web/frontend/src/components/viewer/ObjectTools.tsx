import { useTranslation } from 'react-i18next';
import { usePrintStore } from '../../stores/usePrintStore';

export default function ObjectTools() {
  const { t } = useTranslation();
  const objectSelected = usePrintStore((s) => s.objectSelected);
  const sliceResult = usePrintStore((s) => s.sliceResult);
  const transformMode = usePrintStore((s) => s.transformMode);
  const objectPosition = usePrintStore((s) => s.objectPosition);
  const objectRotation = usePrintStore((s) => s.objectRotation);
  const setTransformMode = usePrintStore((s) => s.setTransformMode);
  const dropToBed = usePrintStore((s) => s.dropToBed);
  const layFlat = usePrintStore((s) => s.layFlat);
  const resetObjectTransform = usePrintStore((s) => s.resetObjectTransform);

  if (!objectSelected || sliceResult) return null;

  const toDeg = (rad: number) => {
    const d = Math.round((rad * 180) / Math.PI) % 360;
    return d < 0 ? d + 360 : d;
  };

  const modeBtn = (mode: 'translate' | 'rotate', label: string, icon: React.ReactNode) => (
    <button
      onClick={() => setTransformMode(mode)}
      className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold transition-colors ${
        transformMode === mode
          ? 'bg-blue-600 text-white'
          : 'bg-black/50 dark:bg-white/10 backdrop-blur text-white dark:text-gray-200 hover:bg-black/70'
      }`}
    >
      {icon}
      {label}
    </button>
  );

  return (
    <div className="absolute left-3 top-1/2 -translate-y-1/2 flex flex-col items-center gap-2 z-10">
      {/* Mode toggle: Translate / Rotate */}
      {modeBtn(
        'translate',
        t('viewer.move'),
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15" />
        </svg>,
      )}

      {modeBtn(
        'rotate',
        t('viewer.rotate'),
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
        </svg>,
      )}

      <hr className="w-8 border-gray-500/40" />

      {/* Lay flat — auto-detect largest face and orient it down */}
      <button
        onClick={layFlat}
        className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold bg-amber-600/80 backdrop-blur text-white hover:bg-amber-500 transition-colors"
        title={t('viewer.layFlat')}
      >
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 18M6 6l6 6 6-6" />
        </svg>
        {t('viewer.layFlat')}
      </button>

      {/* Drop to bed */}
      <button
        onClick={dropToBed}
        className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold bg-green-600/80 backdrop-blur text-white hover:bg-green-500 transition-colors"
        title={t('viewer.dropToBed')}
      >
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 13.5L12 21m0 0l-7.5-7.5M12 21V3" />
        </svg>
        {t('viewer.dropToBed')}
      </button>

      {/* Reset */}
      <button
        onClick={resetObjectTransform}
        className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold bg-black/50 dark:bg-white/10 backdrop-blur text-white dark:text-gray-200 hover:bg-red-600/80 transition-colors"
      >
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 15L3 9m0 0l6-6M3 9h12a6 6 0 010 12h-3" />
        </svg>
        {t('viewer.reset')}
      </button>

      {/* Transform info */}
      <div className="bg-black/60 backdrop-blur rounded-lg px-2 py-1.5 text-[10px] font-mono text-gray-300 leading-relaxed">
        <div className="text-gray-500 text-[9px] uppercase tracking-wider mb-0.5">
          {transformMode === 'translate' ? 'XYZ mm' : 'XYZ °'}
        </div>
        {transformMode === 'translate' ? (
          <>
            <div><span className="text-red-400">X</span> {objectPosition[0].toFixed(1)}</div>
            <div><span className="text-green-400">Y</span> {objectPosition[1].toFixed(1)}</div>
            <div><span className="text-blue-400">Z</span> {objectPosition[2].toFixed(1)}</div>
          </>
        ) : (
          <>
            <div><span className="text-red-400">X</span> {toDeg(objectRotation[0])}°</div>
            <div><span className="text-green-400">Y</span> {toDeg(objectRotation[1])}°</div>
            <div><span className="text-blue-400">Z</span> {toDeg(objectRotation[2])}°</div>
          </>
        )}
      </div>
    </div>
  );
}
