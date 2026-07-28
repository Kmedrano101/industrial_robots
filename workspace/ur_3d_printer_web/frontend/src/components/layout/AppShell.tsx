import { useState, useCallback, useRef, useEffect } from 'react';
import Header from './Header';
import SceneCanvas from '../viewer/SceneCanvas';
import FileUpload from '../controls/FileUpload';
import SliceSettingsPanel from '../controls/SliceSettings';
import PrintControlPanel from '../controls/PrintControlPanel';
import PrintProgress from '../status/PrintProgress';
import ExtruderPanel from '../controls/ExtruderPanel';
import ExtruderStatus from '../status/ExtruderStatus';
import SystemStatus from '../status/SystemStatus';
import RobotPage from '../robot/RobotPage';
import { usePrintStore } from '../../stores/usePrintStore';
import { useSettingsStore } from '../../stores/useSettingsStore';
import { useRobotStore } from '../../stores/useRobotStore';
import { PrintStateEnum } from '../../types/ros';
import { useTranslation } from 'react-i18next';
import Card from '../common/Card';

const MIN_PANEL_WIDTH = 280;
const MAX_PANEL_WIDTH = 700;
const DEFAULT_PANEL_WIDTH = 400;

function LivePanel() {
  const { t } = useTranslation();
  const printState = usePrintStore((s) => s.printState);
  const joints = useRobotStore((s) => s.jointStates.positions);
  const isPrinting =
    printState.state === PrintStateEnum.PRINTING ||
    printState.state === PrintStateEnum.PAUSED ||
    printState.state === PrintStateEnum.TRAVEL_MOVE ||
    printState.state === PrintStateEnum.LAYER_CHANGE;

  const toDeg = (rad: number) => (rad * 180 / Math.PI).toFixed(1);

  return (
    <div className="space-y-4">
      {/* One status card. Previously a "Connection" card and a "Robot state"
         card sat next to each other and could show "Disconnected" in red
         beside "Ready" in green; both now render the same derivation. */}
      <Card title={t('status.title')}>
        <SystemStatus variant="detailed" />
      </Card>

      {/* Joint positions */}
      <Card title={t('live.joints')}>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs font-mono">
          {['Shoulder Pan', 'Shoulder Lift', 'Elbow', 'Wrist 1', 'Wrist 2', 'Wrist 3'].map((name, i) => (
            <div key={name} className="flex justify-between">
              <span className="text-gray-500">{name}</span>
              <span>{toDeg(joints[i] ?? 0)}°</span>
            </div>
          ))}
        </div>
      </Card>

      {/* Print controls */}
      <PrintControlPanel />

      {/* Print progress */}
      {isPrinting && <PrintProgress />}

      {/* Extruder */}
      <Card title={t('extruder.title')}>
        <ExtruderStatus />
      </Card>
    </div>
  );
}

export default function AppShell() {
  const viewMode = useSettingsStore((s) => s.viewMode);
  const page = useSettingsStore((s) => s.page);
  const printState = usePrintStore((s) => s.printState.state);
  const isPrinting =
    printState === PrintStateEnum.PRINTING ||
    printState === PrintStateEnum.PAUSED ||
    printState === PrintStateEnum.TRAVEL_MOVE ||
    printState === PrintStateEnum.LAYER_CHANGE;

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
      const newWidth = Math.min(MAX_PANEL_WIDTH, Math.max(MIN_PANEL_WIDTH, startWidth.current + delta));
      setPanelWidth(newWidth);
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

  if (page === 'robot') {
    return (
      <div className="flex h-full flex-col">
        <Header />
        <RobotPage />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <Header />
      <div className="flex flex-1 flex-col lg:flex-row overflow-hidden relative">
        {/* 3D Viewer */}
        <div className="flex-1 min-h-[300px] min-w-0">
          <SceneCanvas />
        </div>

        {/* Collapse toggle */}
        <button
          onClick={() => setPanelOpen(!panelOpen)}
          className="hidden lg:flex absolute right-0 top-1/2 -translate-y-1/2 z-20 items-center justify-center w-5 h-12 bg-gray-200 dark:bg-gray-800 hover:bg-gray-300 dark:hover:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-l-md transition-colors"
          style={{ right: panelOpen ? panelWidth : 0 }}
        >
          <svg
            className={`w-3 h-3 text-gray-600 dark:text-gray-300 transition-transform ${panelOpen ? '' : 'rotate-180'}`}
            viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </button>

        {/* Panel */}
        {panelOpen && (
          <>
            <div
              onMouseDown={onMouseDown}
              className="hidden lg:block w-1 cursor-col-resize hover:bg-blue-500/50 active:bg-blue-500 transition-colors flex-shrink-0"
            />
            <div
              className="w-full overflow-y-auto border-l border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-950 p-4 flex-shrink-0"
              style={{ width: window.innerWidth >= 1024 ? panelWidth : undefined }}
            >
              {viewMode === 'live' ? (
                <LivePanel />
              ) : (
                <div className="space-y-4">
                  <FileUpload />
                  <SliceSettingsPanel />
                  <PrintControlPanel />
                  {isPrinting && <PrintProgress />}
                  <ExtruderPanel />
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
