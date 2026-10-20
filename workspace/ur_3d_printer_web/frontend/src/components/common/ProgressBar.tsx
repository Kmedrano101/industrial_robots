interface ProgressBarProps {
  value: number; // 0-1
  className?: string;
  color?: string;
}

export default function ProgressBar({
  value,
  className = '',
  color = 'bg-accent',
}: ProgressBarProps) {
  const pct = Math.min(100, Math.max(0, value * 100));
  return (
    <div
      className={`h-2 w-full overflow-hidden rounded-full bg-surface2 ${className}`}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(pct)}
    >
      <div
        className={`h-full rounded-full transition-all duration-300 ${color}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
