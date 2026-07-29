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
        case 'p':
        case 'P':
          useSettingsStore.getState().setPage('printer');
          break;
        case 'r':
        case 'R':
          useSettingsStore.getState().setPage('robot');
          break;
        case '1':
          useSettingsStore.getState().setViewMode('prepare');
          break;
        case '2':
          useSettingsStore.getState().setViewMode('live');
          break;
      }
    }

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);
}
