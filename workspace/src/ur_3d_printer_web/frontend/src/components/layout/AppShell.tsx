import { useState, useCallback, useRef, useEffect } from 'react';
import Header from './Header';
import SceneCanvas from '../viewer/SceneCanvas';
import FileUpload from '../controls/FileUpload';
import SliceSettingsPanel from '../controls/SliceSettings';
import PrintControlPanel from '../controls/PrintControlPanel';
import PrintProgress from '../status/PrintProgress';
import ExtruderPanel from '../controls/ExtruderPanel';
import { usePrintStore } from '../../stores/usePrintStore';
import { PrintStateEnum } from '../../types/ros';

const MIN_PANEL_WIDTH = 280;
const MAX_PANEL_WIDTH = 700;
const DEFAULT_PANEL_WIDTH = 400;

export default function AppShell() {
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

  // Drag-to-resize handler
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

  return (
    <div className="flex h-full flex-col">
      <Header />
      <div className="flex flex-1 flex-col lg:flex-row overflow-hidden relative">
        {/* 3D Viewer — takes all remaining space */}
        <div className="flex-1 min-h-[300px] min-w-0">
          <SceneCanvas />
        </div>

        {/* Collapse / expand toggle — always visible */}
        <button
          onClick={() => setPanelOpen(!panelOpen)}
          className="hidden lg:flex absolute right-0 top-1/2 -translate-y-1/2 z-20 items-center justify-center w-5 h-12 bg-gray-200 dark:bg-gray-800 hover:bg-gray-300 dark:hover:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-l-md transition-colors"
          style={{ right: panelOpen ? panelWidth : 0 }}
          aria-label={panelOpen ? 'Collapse panel' : 'Expand panel'}
        >
          <svg
            className={`w-3 h-3 text-gray-600 dark:text-gray-300 transition-transform ${panelOpen ? '' : 'rotate-180'}`}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={3}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </button>

        {/* Resizable control panel */}
        {panelOpen && (
          <>
            {/* Drag handle */}
            <div
              onMouseDown={onMouseDown}
              className="hidden lg:block w-1 cursor-col-resize hover:bg-blue-500/50 active:bg-blue-500 transition-colors flex-shrink-0"
            />

            {/* Panel content */}
            <div
              className="w-full overflow-y-auto border-l border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-950 p-4 space-y-4 flex-shrink-0"
              style={{ width: window.innerWidth >= 1024 ? panelWidth : undefined }}
            >
              <FileUpload />
              <SliceSettingsPanel />
              <PrintControlPanel />
              {isPrinting && <PrintProgress />}
              <ExtruderPanel />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
