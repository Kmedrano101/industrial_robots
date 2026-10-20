import { lazy, Suspense, useState, useCallback, useRef, useEffect } from 'react';
import SideNav from './SideNav';
import TopBar from './TopBar';
import PreparePanel from './PreparePanel';
import MonitorPanel from './MonitorPanel';
import { useSettingsStore } from '../../stores/useSettingsStore';

// The two views that pull in three.js are loaded on demand, so the
// control panels are interactive before the 3D stack (~800 kB) arrives.
const SceneCanvas = lazy(() => import('../viewer/SceneCanvas'));
const RobotPage = lazy(() => import('../robot/RobotPage'));
const SettingsPage = lazy(() => import('../settings/SettingsPage'));
const JobsPage = lazy(() => import('../jobs/JobsPage'));

function ViewFallback() {
  return (
    <div className="flex h-full w-full items-center justify-center text-sm text-faint" aria-busy="true">
      …
    </div>
  );
}

const MIN_PANEL_WIDTH = 300;
const MAX_PANEL_WIDTH = 720;
const DEFAULT_PANEL_WIDTH = 420;

/** Printer pages: the 3D view with a resizable, collapsible side panel.
 *  Stacks vertically below `lg`, where the panel takes the full width. */
function PrinterLayout({ panel }: { panel: React.ReactNode }) {
  const [panelOpen, setPanelOpen] = useState(true);
  const [panelWidth, setPanelWidth] = useState(DEFAULT_PANEL_WIDTH);
  const dragging = useRef(false);
  const startX = useRef(0);
  const startWidth = useRef(0);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    startX.current = e.clientX;
    startWidth.current = panelWidth;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [panelWidth]);

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!dragging.current) return;
      const delta = startX.current - e.clientX;
      setPanelWidth(Math.min(MAX_PANEL_WIDTH, Math.max(MIN_PANEL_WIDTH, startWidth.current + delta)));
    };
    const onMouseUp = () => {
      if (!dragging.current) return;
      dragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, []);

  return (
    <div className="relative flex flex-1 flex-col overflow-hidden lg:flex-row">
      <div className="min-h-[300px] min-w-0 flex-1">
        <Suspense fallback={<ViewFallback />}>
          <SceneCanvas />
        </Suspense>
      </div>

      {/* Collapse toggle (desktop only) */}
      <button
        onClick={() => setPanelOpen(!panelOpen)}
        aria-label={panelOpen ? 'Collapse panel' : 'Expand panel'}
        className="absolute right-0 top-1/2 z-20 hidden h-12 w-5 -translate-y-1/2 items-center justify-center rounded-l-md border border-r-0 border-line bg-surface text-muted hover:text-ink lg:flex"
        style={{ right: panelOpen ? panelWidth : 0 }}
      >
        <svg
          className={`h-3 w-3 transition-transform ${panelOpen ? '' : 'rotate-180'}`}
          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3} aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
      </button>

      {panelOpen && (
        <>
          <div
            onMouseDown={onMouseDown}
            className="hidden w-1 shrink-0 cursor-col-resize transition-colors hover:bg-accent/50 active:bg-accent lg:block"
          />
          <aside
            className="scroll-thin w-full shrink-0 overflow-y-auto border-l border-line bg-bg p-3 sm:p-4"
            style={{ width: window.innerWidth >= 1024 ? panelWidth : undefined }}
          >
            {panel}
          </aside>
        </>
      )}
    </div>
  );
}

export default function AppShell() {
  const page = useSettingsStore((s) => s.page);

  let content: React.ReactNode;
  switch (page) {
    case 'monitor':
      content = <PrinterLayout panel={<MonitorPanel />} />;
      break;
    case 'robot':
      content = (
        <Suspense fallback={<ViewFallback />}>
          <RobotPage />
        </Suspense>
      );
      break;
    case 'jobs':
      content = (
        <Suspense fallback={<ViewFallback />}>
          <JobsPage />
        </Suspense>
      );
      break;
    case 'settings':
      content = (
        <Suspense fallback={<ViewFallback />}>
          <SettingsPage />
        </Suspense>
      );
      break;
    default:
      content = <PrinterLayout panel={<PreparePanel />} />;
  }

  return (
    <div className="flex h-full">
      <SideNav />
      {/* Bottom padding below lg reserves room for the tab bar. */}
      <div className="flex min-w-0 flex-1 flex-col pb-[60px] lg:pb-0">
        <TopBar />
        <main className="flex min-h-0 flex-1 flex-col">{content}</main>
      </div>
    </div>
  );
}
