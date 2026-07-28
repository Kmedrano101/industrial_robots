interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger';
  size?: 'sm' | 'md';
  /** Why the button is unavailable. Surfaced as a tooltip and to assistive
   *  tech, so a disabled control explains itself instead of leaving the
   *  operator to guess. Ignored when the button is enabled. */
  disabledReason?: string;
}

// Disabled variants deliberately drop saturation as well as contrast. The
// previous `disabled:bg-blue-400` left a disabled primary button looking
// bright and clickable on the dark theme — "Start Print" read as available
// with no file loaded, which is exactly the affordance an HMI must not fake.
const variants = {
  primary:
    'bg-blue-600 hover:bg-blue-700 text-white ' +
    'disabled:bg-gray-200 dark:disabled:bg-gray-800 ' +
    'disabled:text-gray-400 dark:disabled:text-gray-600 ' +
    'disabled:hover:bg-gray-200 dark:disabled:hover:bg-gray-800',
  secondary:
    'bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-900 dark:text-gray-100 ' +
    'disabled:bg-gray-100 dark:disabled:bg-gray-800 ' +
    'disabled:text-gray-400 dark:disabled:text-gray-600 ' +
    'disabled:hover:bg-gray-100 dark:disabled:hover:bg-gray-800',
  danger:
    'bg-red-600 hover:bg-red-700 text-white ' +
    'disabled:bg-gray-200 dark:disabled:bg-gray-800 ' +
    'disabled:text-gray-400 dark:disabled:text-gray-600 ' +
    'disabled:hover:bg-gray-200 dark:disabled:hover:bg-gray-800',
};

const sizes = {
  // 44px minimum height is the touch-target size industrial HMI guidance
  // asks for; this UI gets operated from a tablet next to the machine.
  sm: 'px-3 py-1.5 text-sm min-h-[36px]',
  md: 'px-4 py-2 text-sm min-h-[44px]',
};

export default function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  children,
  disabledReason,
  disabled,
  title,
  ...props
}: ButtonProps) {
  const reason = disabled ? disabledReason : undefined;
  return (
    <button
      disabled={disabled}
      title={reason ?? title}
      aria-disabled={disabled || undefined}
      className={
        'rounded-lg font-medium transition-colors disabled:cursor-not-allowed ' +
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ' +
        'focus-visible:ring-offset-1 dark:focus-visible:ring-offset-gray-900 ' +
        `${variants[variant]} ${sizes[size]} ${className}`
      }
      {...props}
    >
      {children}
    </button>
  );
}
