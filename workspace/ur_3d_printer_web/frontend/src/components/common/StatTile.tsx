import type { Severity } from '../../lib/status';
import { SEVERITY_TEXT } from '../../lib/status';

interface StatTileProps {
  label: string;
  value: React.ReactNode;
  unit?: string;
  /** Colours the value; defaults to plain ink so a dashboard of tiles does
   *  not become a wall of colour. */
  severity?: Severity;
  /** Small line under the value (a secondary reading, an ETA). */
  sub?: React.ReactNode;
  className?: string;
  /** Numbers are mono so digits line up; words (a state name) are not. */
  mono?: boolean;
}

/** One number the operator glances at: label on top, big value, unit. The
 *  monitor view is a row of these; they replace the two-column label/value
 *  lists that needed reading rather than glancing. */
export default function StatTile({ label, value, unit, severity, sub, className = '', mono = true }: StatTileProps) {
  return (
    <div className={`min-w-0 rounded-lg border border-line bg-surface px-3 py-2.5 shadow-card ${className}`}>
      <div className="truncate text-[11px] font-medium uppercase tracking-[0.06em] text-muted">{label}</div>
      <div
        className={`mt-0.5 flex items-baseline gap-1 font-semibold leading-tight ${
          mono ? 'font-mono text-xl' : 'text-base'
        } ${
          severity ? SEVERITY_TEXT[severity] : 'text-ink'
        }`}
      >
        <span className="truncate">{value}</span>
        {unit && <span className="text-xs font-normal text-muted">{unit}</span>}
      </div>
      {sub && <div className="mt-0.5 truncate text-[11px] text-faint">{sub}</div>}
    </div>
  );
}
