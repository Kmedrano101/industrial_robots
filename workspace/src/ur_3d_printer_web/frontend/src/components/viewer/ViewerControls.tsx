import { useTranslation } from 'react-i18next';

interface ViewerControlsProps {
  onCameraPreset: (preset: 'top' | 'front' | 'iso') => void;
}

export default function ViewerControls({ onCameraPreset }: ViewerControlsProps) {
  const { t } = useTranslation();

  return (
    <div className="absolute bottom-3 left-3 flex gap-1 z-10">
      {(['iso', 'top', 'front'] as const).map((preset) => (
        <button
          key={preset}
          onClick={() => onCameraPreset(preset)}
          className="text-xs bg-black/50 dark:bg-white/10 backdrop-blur rounded px-2 py-1 text-white dark:text-gray-200 hover:bg-black/70 transition-colors"
        >
          {t(`viewer.${preset}`)}
        </button>
      ))}
    </div>
  );
}
