import { Suspense, useEffect } from 'react';
import AppShell from './components/layout/AppShell';
import { useWebSocket } from './hooks/useWebSocket';
import { useRobotStatusPoll } from './hooks/useRobotStatusPoll';
import { useEventLogger } from './hooks/useEventLogger';
import { api } from './lib/api';
import { useRobotStore } from './stores/useRobotStore';

function AppContent() {
  useWebSocket();
  // Robot mode/safety/connection status — polled independent of which page
  // is mounted, so it's fresh whether the user is on Printer > Live or the
  // Robot page.
  useRobotStatusPoll();
  // Records state transitions from anywhere in the app, so the log is
  // complete regardless of which page is open.
  useEventLogger();

  // Bootstrap the `test_panel_enabled` flag from /api/health so the
  // ViewModeToggle can decide whether to render the Test tab. Health is
  // cheap and stable; refresh on a 30 s cadence to pick up backend
  // restarts that toggle the env.
  useEffect(() => {
    let alive = true;
    async function poll() {
      try {
        const h = await api.get<{ test_panel_enabled?: boolean }>('/health');
        if (alive) {
          useRobotStore.getState().setTestPanelEnabled(Boolean(h.test_panel_enabled));
        }
      } catch {
        /* offline; will retry */
      }
    }
    poll();
    const id = window.setInterval(poll, 30_000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, []);

  return <AppShell />;
}

export default function App() {
  return (
    <Suspense fallback={<div className="flex h-full items-center justify-center">Loading...</div>}>
      <AppContent />
    </Suspense>
  );
}
