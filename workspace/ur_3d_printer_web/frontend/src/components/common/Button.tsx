interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  /** Why the button is unavailable. Surfaced as a tooltip and to assistive
   *  tech, so a disabled control explains itself instead of leaving the
   *  operator to guess. Ignored when the button is enabled. */
  disabledReason?: string;
  /** Leading icon; sized by the button. */
  icon?: React.ReactNode;
}

// Disabled variants deliberately drop saturation as well as contrast: a
// disabled primary button must not read as available ("Start Print" with
// nothing loaded is exactly the affordance an HMI must not fake).
const DISABLED =
  'disabled:cursor-not-allowed disabled:bg-surface2 disabled:text-faint ' +
  'disabled:border-transparent disabled:shadow-none disabled:hover:bg-surface2';

const variants = {
  primary: 'bg-accent text-accent-fg border-transparent hover:brightness-110 shadow-card',
  secondary: 'bg-surface2 text-ink border-transparent hover:bg-line/70',
  outline: 'bg-transparent text-ink border-line hover:bg-surface2',
  ghost: 'bg-transparent text-muted border-transparent hover:bg-surface2 hover:text-ink',
  danger: 'bg-danger text-white border-transparent hover:brightness-110 shadow-card',
};

const sizes = {
  // 44 px is the touch-target size industrial HMI guidance asks for; this
  // UI is operated from a tablet next to the machine. `sm` is for dense,
  // secondary controls only.
  sm: 'min-h-[36px] px-3 text-[13px] gap-1.5 [&_svg]:h-4 [&_svg]:w-4',
  md: 'min-h-touch px-4 text-sm gap-2 [&_svg]:h-4 [&_svg]:w-4',
  lg: 'min-h-[52px] px-5 text-base gap-2 [&_svg]:h-5 [&_svg]:w-5',
};

export default function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  children,
  disabledReason,
  disabled,
  title,
  icon,
  ...props
}: ButtonProps) {
  const reason = disabled ? disabledReason : undefined;
  return (
    <button
      disabled={disabled}
      title={reason ?? title}
      aria-disabled={disabled || undefined}
      className={
        'inline-flex items-center justify-center rounded-lg border font-medium ' +
        'transition-[background-color,color,filter] duration-150 select-none ' +
        `${variants[variant]} ${sizes[size]} ${DISABLED} ${className}`
      }
      {...props}
    >
      {icon}
      {children}
    </button>
  );
}
