import { useTranslation } from 'react-i18next';

interface ViewerControlsProps {
  onCameraPreset: (preset: 'top' | 'front' | 'iso') => void;
}

const ICONS = {
  iso: (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 7.5l-9-5.25L3 7.5m18 0l-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9" />
    </svg>
  ),
  top: (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5a1.5 1.5 0 001.5-1.5V4.5a1.5 1.5 0 00-1.5-1.5H3.75a1.5 1.5 0 00-1.5 1.5v15a1.5 1.5 0 001.5 1.5z" />
    </svg>
  ),
  front: (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h12A2.25 2.25 0 0120.25 6v12A2.25 2.25 0 0118 20.25H6A2.25 2.25 0 013.75 18V6z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6l8.25 6 8.25-6" />
    </svg>
  ),
};

export default function ViewerControls({ onCameraPreset }: ViewerControlsProps) {
  const { t } = useTranslation();

  return (
    <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex items-center gap-0.5 rounded-xl bg-black/60 dark:bg-black/70 backdrop-blur-md p-1 border border-white/10 z-10">
      {(['iso', 'top', 'front'] as const).map((preset) => (
        <button
          key={preset}
          onClick={() => onCameraPreset(preset)}
          className="group relative flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-white/10 hover:text-white transition-all duration-150"
        >
          {ICONS[preset]}
          <span>{t(`viewer.${preset}`)}</span>
        </button>
      ))}
    </div>
  );
}
