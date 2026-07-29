import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { usePrintStore } from '../../stores/usePrintStore';
import { SEVERITY_TEXT } from '../../lib/status';
import Card from '../common/Card';

/**
 * Timestamped record of what the system did.
 *
 * Feedback used to be a single line that appeared and was overwritten by
 * the next one, so anything that happened while the operator was looking at
 * the machine instead of the screen was simply lost — which during
 * commissioning is most of the time. Keeping the last N entries with times
 * makes a failure reconstructable after the fact.
 */

const LEVEL_TEXT = {
  info: SEVERITY_TEXT.neutral,
  warn: SEVERITY_TEXT.warn,
  error: SEVERITY_TEXT.danger,
} as const;

function clock(t: number): string {
  return new Date(t).toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export default function EventLog() {
  const { t } = useTranslation();
  const entries = usePrintStore((s) => s.eventLog);
  const clearLog = usePrintStore((s) => s.clearLog);
  const scrollRef = useRef<HTMLDivElement>(null);
  const pinnedToBottom = useRef(true);

  // Follow new entries, but stop following the moment the operator scrolls
  // up — yanking them back to the bottom mid-read is worse than no
  // autoscroll at all.
  useEffect(() => {
    const el = scrollRef.current;
    if (el && pinnedToBottom.current) el.scrollTop = el.scrollHeight;
  }, [entries]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    pinnedToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
  };

  return (
    <Card title={t('log.title')} collapsible defaultCollapsed>
      {entries.length === 0 ? (
        <p className="text-xs text-gray-500">{t('log.empty')}</p>
      ) : (
        <>
          <div
            ref={scrollRef}
            onScroll={onScroll}
            className="max-h-48 overflow-y-auto rounded-md bg-gray-50 dark:bg-gray-950 p-2 font-mono text-[11px] leading-relaxed"
          >
            {entries.map((e, i) => (
              <div key={`${e.t}-${i}`} className="flex gap-2">
                <span className="shrink-0 text-gray-400 dark:text-gray-600">{clock(e.t)}</span>
                <span className={LEVEL_TEXT[e.level]}>{e.message}</span>
              </div>
            ))}
          </div>
          <button
            onClick={clearLog}
            className="mt-2 text-[11px] text-gray-500 underline-offset-2 hover:underline"
          >
            {t('log.clear')}
          </button>
        </>
      )}
    </Card>
  );
}
