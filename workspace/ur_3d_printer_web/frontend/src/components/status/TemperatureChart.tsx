import { useTranslation } from 'react-i18next';
import { usePrintStore } from '../../stores/usePrintStore';

/**
 * Extruder temperature trace, actual against target.
 *
 * A single instantaneous "0°C / 0°C" readout cannot answer the questions
 * that matter while commissioning a first layer: is it still climbing, did
 * it overshoot, is it holding, did it dip when the fan came on. Every
 * printer web UI (Mainsail, Fluidd, OctoPrint) puts this trace on the main
 * view for that reason.
 *
 * Hand-drawn SVG rather than a charting library: the whole series is a few
 * hundred points, and the app ships under a strict CSP with no external
 * hosts, so avoiding another dependency is worth more than the features a
 * library would add.
 */

const W = 260;
const H = 64;
const PAD = 2;

export default function TemperatureChart() {
  const { t } = useTranslation();
  const history = usePrintStore((s) => s.temperatureHistory);
  const extruder = usePrintStore((s) => s.extruderState);

  if (history.length < 2) {
    return (
      <p className="text-xs text-gray-500">{t('temperature.waiting')}</p>
    );
  }

  // Scale to the data, but never to a degenerate range: with the extruder
  // off every sample is 0 and a naive min/max would divide by zero.
  const values = history.flatMap((s) => [s.temp, s.target]);
  const rawMax = Math.max(...values);
  const rawMin = Math.min(...values);
  const max = Math.max(rawMax, rawMin + 10);
  const min = Math.min(rawMin, max - 10);
  const span = max - min;

  const x = (i: number) => PAD + (i / (history.length - 1)) * (W - 2 * PAD);
  const y = (v: number) => H - PAD - ((v - min) / span) * (H - 2 * PAD);

  const path = (pick: (s: (typeof history)[number]) => number) =>
    history.map((s, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(pick(s)).toFixed(1)}`).join(' ');

  const spanSeconds = Math.round((history[history.length - 1].t - history[0].t) / 1000);

  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <span className="font-mono text-lg font-semibold text-gray-800 dark:text-gray-100">
          {extruder.temperature.toFixed(0)}°C
        </span>
        <span className="text-xs text-gray-500">
          {t('temperature.target')} {extruder.target_temperature.toFixed(0)}°C
        </span>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label={t('temperature.ariaLabel', {
          temp: extruder.temperature.toFixed(0),
          target: extruder.target_temperature.toFixed(0),
        })}
        preserveAspectRatio="none"
      >
        {/* target: dashed, deliberately quieter than the measured trace */}
        <path
          d={path((s) => s.target)}
          fill="none"
          stroke="currentColor"
          strokeWidth="1"
          strokeDasharray="3 3"
          className="text-gray-400 dark:text-gray-600"
        />
        <path
          d={path((s) => s.temp)}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          className="text-amber-500"
        />
      </svg>

      <div className="flex justify-between text-[10px] text-gray-500">
        <span>−{spanSeconds}s</span>
        <span>{min.toFixed(0)}–{max.toFixed(0)}°C</span>
        <span>{t('temperature.now')}</span>
      </div>
    </div>
  );
}
