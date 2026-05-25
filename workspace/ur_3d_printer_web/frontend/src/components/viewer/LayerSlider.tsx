import { useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { usePrintStore } from '../../stores/usePrintStore';

export default function LayerSlider() {
  const { t } = useTranslation();
  const sliceResult = usePrintStore((s) => s.sliceResult);
  const visibleMax = usePrintStore((s) => s.visibleLayerMax);
  const isAnimating = usePrintStore((s) => s.isLayerAnimating);
  const setVisibleLayerMax = usePrintStore((s) => s.setVisibleLayerMax);
  const setIsLayerAnimating = usePrintStore((s) => s.setIsLayerAnimating);
  const animationRef = useRef<ReturnType<typeof setInterval>>();

  const totalLayers = sliceResult?.numLayers ?? 0;
  const currentZ = sliceResult?.layers[Math.min(visibleMax - 1, totalLayers - 1)]?.z ?? 0;

  // Keyboard controls
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!sliceResult) return;
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setVisibleLayerMax(Math.min(visibleMax + 1, totalLayers));
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        setVisibleLayerMax(Math.max(visibleMax - 1, 0));
      }
    },
    [sliceResult, visibleMax, totalLayers, setVisibleLayerMax],
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Auto-animate
  useEffect(() => {
    if (isAnimating) {
      setVisibleLayerMax(0);
      animationRef.current = setInterval(() => {
        const current = usePrintStore.getState().visibleLayerMax;
        const total = usePrintStore.getState().sliceResult?.numLayers ?? 0;
        if (current >= total) {
          setIsLayerAnimating(false);
        } else {
          setVisibleLayerMax(current + 1);
        }
      }, 100);
    } else {
      clearInterval(animationRef.current);
    }
    return () => clearInterval(animationRef.current);
  }, [isAnimating, setVisibleLayerMax, setIsLayerAnimating]);

  if (!sliceResult || totalLayers === 0) return null;

  return (
    <div className="absolute right-3 top-1/2 -translate-y-1/2 flex flex-col items-center gap-2 z-10">
      {/* Layer info */}
      <div className="text-xs text-center bg-black/50 dark:bg-white/10 backdrop-blur rounded px-2 py-1 text-white dark:text-gray-200 whitespace-nowrap">
        {t('viewer.layerSlider', {
          layer: visibleMax,
          total: totalLayers,
          z: currentZ.toFixed(1),
        })}
      </div>

      {/* Vertical slider (rotated range input) */}
      <input
        type="range"
        min={0}
        max={totalLayers}
        value={visibleMax}
        onChange={(e) => setVisibleLayerMax(parseInt(e.target.value))}
        className="h-48 appearance-none cursor-pointer"
        style={{
          writingMode: 'vertical-lr',
          direction: 'rtl',
        }}
      />

      {/* Play/stop button */}
      <button
        onClick={() => setIsLayerAnimating(!isAnimating)}
        className="text-xs bg-black/50 dark:bg-white/10 backdrop-blur rounded px-2 py-1 text-white dark:text-gray-200 hover:bg-black/70 transition-colors"
      >
        {isAnimating ? t('viewer.stop') : t('viewer.play')}
      </button>
    </div>
  );
}
