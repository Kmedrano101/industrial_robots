import { useEffect } from 'react';
import { usePrintStore } from '../stores/usePrintStore';
import { useSettingsStore } from '../stores/useSettingsStore';
import { PrintStateEnum } from '../types/ros';
import { api } from '../lib/api';

/**
 * Keyboard shortcuts for the operations an operator repeats.
 *
 * Deliberately conservative about which actions get a key: pause and resume
 * are recoverable, so they are bound. Starting a print and anything that
 * moves the robot are not — a stray keypress must never set the machine in
 * motion, which is the same reasoning behind the explicit arming gate on
 * the Robot page.
 *
 *   Space   pause / resume (only while printing or paused)
 *   1..4    Prepare / Monitor / Robot / Settings
 */
export function useKeyboardShortcuts() {
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      // Never hijack typing.
      const el = e.target as HTMLElement | null;
      if (
        el &&
        (el.tagName === 'INPUT' ||
          el.tagName === 'TEXTAREA' ||
          el.tagName === 'SELECT' ||
          el.isContentEditable)
      ) {
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey) return;

      const state = usePrintStore.getState().printState.state;
      const { setPage } = useSettingsStore.getState();

      switch (e.key) {
        case ' ': {
          // Space toggles pause/resume, but only when a print is actually
          // running or held — otherwise it does nothing rather than
          // guessing at an intent.
          if (state === PrintStateEnum.PRINTING) {
            e.preventDefault();
            api.post('/print/pause').catch(() => {});
          } else if (state === PrintStateEnum.PAUSED) {
            e.preventDefault();
            api.post('/print/resume').catch(() => {});
          }
          break;
        }
        case '1':
          setPage('prepare');
          break;
        case '2':
          setPage('monitor');
          break;
        case '3':
          setPage('robot');
          break;
        case '4':
          setPage('settings');
          break;
      }
    }

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);
}
