import { useTranslation } from 'react-i18next';
import { usePrintStore } from '../../stores/usePrintStore';

interface ToolButtonProps {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  active?: boolean;
}

function ToolButton({ icon, label, onClick, active = false }: ToolButtonProps) {
  return (
    <button
      onClick={onClick}
      className={`group relative flex items-center justify-center w-10 h-10 rounded-xl transition-all duration-150 ${
        active
          ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/30 ring-2 ring-blue-400/50'
          : 'bg-gray-800/80 dark:bg-gray-700/80 text-gray-300 hover:bg-gray-700 dark:hover:bg-gray-600 hover:text-white'
      }`}
    >
      {icon}
      {/* Tooltip on hover */}
      <span className="pointer-events-none absolute left-full ml-2.5 whitespace-nowrap rounded-lg bg-gray-900 dark:bg-gray-800 px-2.5 py-1.5 text-xs font-medium text-white opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg border border-gray-700/50">
        {label}
      </span>
    </button>
  );
}

export default function ObjectTools() {
  const { t } = useTranslation();
  const objectSelected = usePrintStore((s) => s.objectSelected);
  const sliceResult = usePrintStore((s) => s.sliceResult);
  const transformMode = usePrintStore((s) => s.transformMode);
  const setTransformMode = usePrintStore((s) => s.setTransformMode);
  const dropToBed = usePrintStore((s) => s.dropToBed);
  const layFlat = usePrintStore((s) => s.layFlat);
  const resetObjectTransform = usePrintStore((s) => s.resetObjectTransform);

  if (!objectSelected || sliceResult) return null;

  return (
    <div className="absolute left-3 top-1/2 -translate-y-1/2 z-10 flex flex-col items-center gap-1.5 rounded-2xl bg-black/60 dark:bg-black/70 backdrop-blur-md p-1.5 border border-white/10">
      {/* Move */}
      <ToolButton
        active={transformMode === 'translate'}
        onClick={() => setTransformMode('translate')}
        label={t('viewer.move')}
        icon={
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v18m0-18l-3 3m3-3l3 3m-3 15l-3-3m3 3l3-3M3 12h18m-18 0l3-3m-3 3l3 3m15-3l-3-3m3 3l-3 3" />
          </svg>
        }
      />

      {/* Rotate */}
      <ToolButton
        active={transformMode === 'rotate'}
        onClick={() => setTransformMode('rotate')}
        label={t('viewer.rotate')}
        icon={
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 12c0-4.136-3.364-7.5-7.5-7.5S4.5 7.864 4.5 12" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 9l3-3m0 0l3 3m-3-3v.001" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12c0 4.136 3.364 7.5 7.5 7.5s7.5-3.364 7.5-7.5" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 15l-3 3m0 0l-3-3m3 3v-.001" />
          </svg>
        }
      />

      {/* Divider */}
      <div className="w-6 h-px bg-white/20 my-0.5" />

      {/* Lay Flat */}
      <ToolButton
        onClick={layFlat}
        label={t('viewer.layFlat')}
        icon={
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 20h18" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v10m0 0l-4-4m4 4l4-4" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 16h12" />
          </svg>
        }
      />

      {/* Drop to Bed */}
      <ToolButton
        onClick={dropToBed}
        label={t('viewer.dropToBed')}
        icon={
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v14m0 0l-5-5m5 5l5-5" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 21h16" />
          </svg>
        }
      />

      {/* Divider */}
      <div className="w-6 h-px bg-white/20 my-0.5" />

      {/* Reset */}
      <ToolButton
        onClick={resetObjectTransform}
        label={t('viewer.reset')}
        icon={
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 15L3 9m0 0l6-6M3 9h12a6 6 0 010 12h-3" />
          </svg>
        }
      />
    </div>
  );
}
