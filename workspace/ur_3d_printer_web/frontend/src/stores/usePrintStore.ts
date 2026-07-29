import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type {
  PrintProgress,
  PrintState,
  ExtruderState,
  ToolpathLayer,
} from '../types/ros';
import { PrintStateEnum, ExtruderStateEnum } from '../types/ros';

interface UploadedFile {
  filepath: string;
  filename: string;
  size: number;
  boundingBox: Record<string, number> | null;
  triangleCount: number | null;
}

interface SliceResult {
  gcodeFilepath: string;
  numLayers: number;
  estimatedTime: number;
  layers: ToolpathLayer[];
  nozzleDiameter: number;
  material: string;
}

/** One sampled point of the extruder temperature trace. */
export interface TempSample {
  /** ms since epoch */
  t: number;
  temp: number;
  target: number;
}

/** One line of the operator-visible event log. */
export interface LogEntry {
  t: number;
  level: 'info' | 'warn' | 'error';
  message: string;
}

/** Rolling window sizes. Both are in-memory only and deliberately bounded:
 *  an unbounded trace would grow without limit during a multi-hour print,
 *  and neither is persisted (localStorage has already been overflowed once
 *  in this app by persisting heavy slice data). */
export const TEMP_HISTORY_MAX = 600;   // ~10 min at 1 Hz
export const LOG_MAX = 200;

interface PrintStoreState {
  // ROS2 state from WebSocket
  printState: PrintState;
  temperatureHistory: TempSample[];
  eventLog: LogEntry[];
  printProgress: PrintProgress;
  extruderState: ExtruderState;

  // Upload & slice
  uploadedFile: UploadedFile | null;
  sliceResult: SliceResult | null;
  isSlicing: boolean;
  isUploading: boolean;

  // Object transform on print bed
  objectSelected: boolean;
  objectPosition: [number, number, number];
  objectRotation: [number, number, number]; // [x, y, z] radians
  transformMode: 'translate' | 'rotate';
  dropToBedCounter: number;
  layFlatCounter: number;
  resetCounter: number;

  // Layer slider
  visibleLayerMax: number;
  isLayerAnimating: boolean;

  // Actions
  setPrintState: (state: PrintState) => void;
  setPrintProgress: (progress: PrintProgress) => void;
  setExtruderState: (state: ExtruderState) => void;
  addLogEntry: (level: LogEntry['level'], message: string) => void;
  clearLog: () => void;
  setUploadedFile: (file: UploadedFile | null) => void;
  setSliceResult: (result: SliceResult | null) => void;
  setIsSlicing: (v: boolean) => void;
  setIsUploading: (v: boolean) => void;
  setObjectSelected: (v: boolean) => void;
  setObjectPosition: (pos: [number, number, number]) => void;
  setObjectRotation: (rot: [number, number, number]) => void;
  setTransformMode: (mode: 'translate' | 'rotate') => void;
  rotateObject: (axis: 'x' | 'y' | 'z', degrees: number) => void;
  dropToBed: () => void;
  layFlat: () => void;
  resetObjectTransform: () => void;
  setVisibleLayerMax: (layer: number) => void;
  setIsLayerAnimating: (v: boolean) => void;
  reset: () => void;
}

const initialPrintState: PrintState = {
  state: PrintStateEnum.IDLE,
  state_name: 'IDLE',
  error_message: '',
};

const initialProgress: PrintProgress = {
  current_layer: 0,
  total_layers: 0,
  layer_progress: 0,
  overall_progress: 0,
  elapsed_time: 0,
  estimated_remaining: 0,
  current_z_height: 0,
};

const initialExtruder: ExtruderState = {
  state: ExtruderStateEnum.OFF,
  extrusion_rate: 0,
  temperature: 0,
  target_temperature: 0,
  at_temperature: false,
};

export const usePrintStore = create<PrintStoreState>()(
  persist(
    (set) => ({
  printState: initialPrintState,
  printProgress: initialProgress,
  extruderState: initialExtruder,
  temperatureHistory: [],
  eventLog: [],
  uploadedFile: null,
  sliceResult: null,
  isSlicing: false,
  isUploading: false,
  objectSelected: false,
  objectPosition: [0, 0, 0] as [number, number, number],
  objectRotation: [0, 0, 0] as [number, number, number],
  transformMode: 'translate' as const,
  dropToBedCounter: 0,
  layFlatCounter: 0,
  resetCounter: 0,
  visibleLayerMax: 0,
  isLayerAnimating: false,

  setPrintState: (printState) => set({ printState }),
  setPrintProgress: (printProgress) => set({ printProgress }),
  setExtruderState: (extruderState) =>
    set((state) => {
      const sample: TempSample = {
        t: Date.now(),
        temp: extruderState.temperature,
        target: extruderState.target_temperature,
      };
      const history = [...state.temperatureHistory, sample];
      return {
        extruderState,
        temperatureHistory:
          history.length > TEMP_HISTORY_MAX
            ? history.slice(history.length - TEMP_HISTORY_MAX)
            : history,
      };
    }),
  addLogEntry: (level, message) =>
    set((state) => {
      const last = state.eventLog[state.eventLog.length - 1];
      // Collapse consecutive identical messages: the print state is
      // republished continuously, and a log that repeats one line hundreds
      // of times hides everything else.
      if (last && last.message === message && last.level === level) return {};
      const next = [...state.eventLog, { t: Date.now(), level, message }];
      return {
        eventLog: next.length > LOG_MAX ? next.slice(next.length - LOG_MAX) : next,
      };
    }),
  clearLog: () => set({ eventLog: [] }),
  setUploadedFile: (uploadedFile) =>
    set({ uploadedFile, sliceResult: null, visibleLayerMax: 0 }),
  setSliceResult: (sliceResult) =>
    set({
      sliceResult,
      visibleLayerMax: sliceResult ? sliceResult.numLayers : 0,
    }),
  setIsSlicing: (isSlicing) => set({ isSlicing }),
  setIsUploading: (isUploading) => set({ isUploading }),
  setObjectSelected: (objectSelected) => set({ objectSelected }),
  setObjectPosition: (objectPosition) => set({ objectPosition }),
  setObjectRotation: (objectRotation) => set({ objectRotation }),
  setTransformMode: (transformMode) => set({ transformMode }),
  rotateObject: (axis, degrees) =>
    set((state) => {
      const rad = (degrees * Math.PI) / 180;
      const rot: [number, number, number] = [...state.objectRotation];
      const i = axis === 'x' ? 0 : axis === 'y' ? 1 : 2;
      rot[i] = rot[i] + rad;
      return { objectRotation: rot };
    }),
  dropToBed: () => set((s) => ({ dropToBedCounter: s.dropToBedCounter + 1 })),
  layFlat: () => set((s) => ({ layFlatCounter: s.layFlatCounter + 1 })),
  resetObjectTransform: () => set((s) => ({
    objectPosition: [0, 0, 0],
    objectRotation: [0, 0, 0],
    dropToBedCounter: 0,
    layFlatCounter: 0,
    resetCounter: s.resetCounter + 1,
  })),
  setVisibleLayerMax: (visibleLayerMax) => set({ visibleLayerMax }),
  setIsLayerAnimating: (isLayerAnimating) => set({ isLayerAnimating }),
  reset: () =>
    set({
      uploadedFile: null,
      sliceResult: null,
      isSlicing: false,
      isUploading: false,
      objectSelected: false,
      objectPosition: [0, 0, 0] as [number, number, number],
      objectRotation: [0, 0, 0] as [number, number, number],
      transformMode: 'translate' as const,
      dropToBedCounter: 0,
      layFlatCounter: 0,
      visibleLayerMax: 0,
      isLayerAnimating: false,
    }),
    }),
    {
      name: 'ur-3d-printer-session',
      // Only persist lightweight state. The slice result is intentionally
      // omitted: with infill patterns the `layers[*].points[*]` array can
      // grow to several MB per slice and easily blow past the localStorage
      // quota (~5 MB). The user has to click "Slice" again after a refresh,
      // which is fast and avoids data-loss surprises.
      partialize: (state) => ({
        uploadedFile: state.uploadedFile,
        objectPosition: state.objectPosition,
        objectRotation: state.objectRotation,
        transformMode: state.transformMode,
        visibleLayerMax: state.visibleLayerMax,
      }),
    },
  ),
);
