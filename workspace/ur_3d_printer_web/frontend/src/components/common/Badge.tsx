import type { Severity } from '../../lib/status';

interface BadgeProps {
  severity?: Severity;
  children: React.ReactNode;
  className?: string;
  /** Leading status dot. */
  dot?: boolean;
  /** Mono for machine identifiers (mode names, controller names). */
  mono?: boolean;
}

/** Tinted pill: a soft background in the severity hue with legible text in
 *  both themes. The old solid pills (white-on-red, black-on-amber) shouted
 *  on a dashboard full of them. */
const STYLES: Record<Severity, string> = {
  ok: 'bg-ok/15 text-ok',
  warn: 'bg-warn/15 text-warn',
  danger: 'bg-danger/15 text-danger',
  neutral: 'bg-surface2 text-muted',
};

const DOT: Record<Severity, string> = {
  ok: 'bg-ok',
  warn: 'bg-warn',
  danger: 'bg-danger',
  neutral: 'bg-faint',
};

export default function Badge({
  severity = 'neutral',
  children,
  className = '',
  dot = false,
  mono = false,
}: BadgeProps) {
  return (
    <span
      className={`inline-flex max-w-full items-center gap-1.5 truncate rounded-full px-2.5 py-0.5 text-xs font-semibold ${
        mono ? 'font-mono font-medium' : ''
      } ${STYLES[severity]} ${className}`}
    >
      {dot && <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${DOT[severity]}`} aria-hidden="true" />}
      <span className="truncate">{children}</span>
    </span>
  );
}
