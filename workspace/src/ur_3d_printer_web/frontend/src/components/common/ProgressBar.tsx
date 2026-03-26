interface ProgressBarProps {
  value: number; // 0-1
  className?: string;
  color?: string;
}

export default function ProgressBar({
  value,
  className = '',
  color = 'bg-blue-600',
}: ProgressBarProps) {
  const pct = Math.min(100, Math.max(0, value * 100));
  return (
    <div
      className={`h-2 w-full rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden ${className}`}
    >
      <div
        className={`h-full rounded-full transition-all duration-300 ${color}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
