import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { usePrintStore } from '../stores/usePrintStore';
import { PrintStateEnum } from '../types/ros';

/**
 * Desktop notification when a print finishes or fails.
 *
 * Prints run for hours and nobody watches the tab for that long, so the two
 * transitions worth interrupting for are completion and error. Nothing else
 * notifies: a notification per state change would be noise and would get
 * muted, taking the two useful ones with it.
 *
 * Permission is never requested on load — an unprompted permission dialog
 * before the user has started anything is the pattern browsers added
 * blocking for. It is requested the first time a print actually starts, and
 * a denial is simply respected: the in-app event log already records the
 * same transitions.
 */
export function usePrintNotifications() {
  const { t } = useTranslation();
  const state = usePrintStore((s) => s.printState.state);
  const errorMessage = usePrintStore((s) => s.printState.error_message);
  const prevState = useRef<PrintStateEnum | null>(null);

  useEffect(() => {
    const supported = typeof window !== 'undefined' && 'Notification' in window;
    const previous = prevState.current;
    prevState.current = state;

    if (!supported) return;

    // Ask only once a print is genuinely underway.
    if (state === PrintStateEnum.PRINTING && Notification.permission === 'default') {
      Notification.requestPermission().catch(() => {});
      return;
    }

    if (previous === null || previous === state) return;
    if (Notification.permission !== 'granted') return;

    if (state === PrintStateEnum.COMPLETED) {
      new Notification(t('notify.completedTitle'), { body: t('notify.completedBody') });
    } else if (state === PrintStateEnum.ERROR) {
      new Notification(t('notify.errorTitle'), {
        body: errorMessage || t('notify.errorBody'),
      });
    }
  }, [state, errorMessage, t]);
}
