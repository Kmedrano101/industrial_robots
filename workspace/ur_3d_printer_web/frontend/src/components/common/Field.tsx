import { useId } from 'react';

/** Shared control styling, so inputs and selects look the same wherever
 *  they appear. Height matches `Button` size `sm` for inline alignment. */
export const CONTROL_CLASS =
  'block w-full min-h-[38px] rounded-lg border border-line bg-surface px-3 text-sm text-ink ' +
  'placeholder:text-faint hover:border-faint focus:border-accent focus:outline-none ' +
  'focus:ring-2 focus:ring-accent/30 disabled:bg-surface2 disabled:text-faint';

interface FieldProps {
  label: string;
  /** Short text after the label: a unit, a valid range. */
  hint?: string;
  /** Inline validation or guidance under the control. */
  help?: string;
  /** Marks `help` as a warning. */
  warn?: boolean;
  className?: string;
  children: (id: string) => React.ReactNode;
}

/** Label + control + help, with the label wired to the control by id. */
export default function Field({ label, hint, help, warn = false, className = '', children }: FieldProps) {
  const id = useId();
  return (
    <div className={`min-w-0 ${className}`}>
      <label htmlFor={id} className="mb-1 flex items-baseline justify-between gap-2 text-xs text-muted">
        <span className="truncate">{label}</span>
        {hint && <span className="shrink-0 font-mono text-[11px] text-faint">{hint}</span>}
      </label>
      {children(id)}
      {help && (
        <p className={`mt-1 text-[11px] ${warn ? 'text-warn' : 'text-faint'}`}>{help}</p>
      )}
    </div>
  );
}

type InputProps = React.InputHTMLAttributes<HTMLInputElement>;
export function Input({ className = '', ...props }: InputProps) {
  return <input className={`${CONTROL_CLASS} ${className}`} {...props} />;
}

type SelectProps = React.SelectHTMLAttributes<HTMLSelectElement>;
export function Select({ className = '', children, ...props }: SelectProps) {
  return (
    <select className={`${CONTROL_CLASS} pr-8 ${className}`} {...props}>
      {children}
    </select>
  );
}

interface SegmentedProps<T extends string> {
  value: T;
  options: { value: T; label: React.ReactNode; disabled?: boolean; title?: string }[];
  onChange: (value: T) => void;
  className?: string;
  /** Visual weight of the selected segment. `danger` is for arming-type
   *  choices (LIVE robot). */
  tone?: 'accent' | 'danger';
  size?: 'sm' | 'md';
  /** Segments share the width equally (for a full-width control with
   *  short labels). Off by default: segments size to their label and the
   *  group wraps, so nothing gets truncated. */
  stretch?: boolean;
  'aria-label'?: string;
}

/** Mutually exclusive choice rendered as one control (theme, language,
 *  simulation/live, view presets). Replaces four hand-rolled copies. */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  className = '',
  tone = 'accent',
  size = 'md',
  stretch = false,
  ...rest
}: SegmentedProps<T>) {
  const selected = tone === 'danger' ? 'bg-danger text-white shadow-card' : 'bg-accent text-accent-fg shadow-card';
  const h = size === 'sm' ? 'min-h-[32px] px-2.5 text-xs' : 'min-h-[40px] px-3 text-sm';
  return (
    <div
      role="radiogroup"
      aria-label={rest['aria-label']}
      className={`inline-flex max-w-full flex-wrap items-center gap-0.5 rounded-lg bg-surface2 p-0.5 ${className}`}
    >
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            disabled={o.disabled}
            title={o.title}
            onClick={() => onChange(o.value)}
            className={`${stretch ? 'flex-1' : 'shrink-0'} whitespace-nowrap rounded-md font-medium transition-colors ${h} ${
              active
                ? selected
                : o.disabled
                ? 'cursor-not-allowed text-faint'
                : 'text-muted hover:text-ink'
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
