import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { usePrintStore } from '../../stores/usePrintStore';
import { useRobotStore } from '../../stores/useRobotStore';
import { PrintStateEnum } from '../../types/ros';
import { api, ApiError } from '../../lib/api';
import Card from '../common/Card';
import Button from '../common/Button';

interface StartResponse {
  success: boolean;
  message: string;
  data?: { num_layers?: number; estimated_time?: number };
}

export default function PrintControlPanel() {
  const { t } = useTranslation();
  const { printState, sliceResult, uploadedFile } = usePrintStore();
  const robotConnected = useRobotStore((s) => s.robotConnected);
  const state = printState.state;
  // StartPrint parses and validates the whole toolpath before answering
  // (tens of seconds): the button must say so, or the operator presses it
  // again — or worse, assumes it did nothing.
  const [starting, setStarting] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; text: string } | null>(null);

  // Each gate reports WHY it blocks, so a greyed-out control explains itself
  // instead of being a dead end. Order matters: name the most fundamental
  // missing precondition first.
  const startBlockedReason = !robotConnected
    ? t('controls.blocked.noRobot')
    : !sliceResult
    ? t('controls.blocked.notSliced')
    : state !== PrintStateEnum.IDLE
    ? t('controls.blocked.busy')
    : null;

  const calibrateBlockedReason = !robotConnected
    ? t('controls.blocked.noRobot')
    : state !== PrintStateEnum.IDLE
    ? t('controls.blocked.busy')
    : null;

  const canStart = startBlockedReason === null && !starting;
  const canPause = state === PrintStateEnum.PRINTING;
  const canResume = state === PrintStateEnum.PAUSED;
  const canCancel = state === PrintStateEnum.PRINTING || state === PrintStateEnum.PAUSED;

  const handleStart = async () => {
    if (!sliceResult) return;
    setStarting(true);
    setFeedback(null);
    try {
      const r = await api.post<StartResponse>('/print/start', {
        gcode_filepath: sliceResult.gcodeFilepath,
        // Recorded in the job history; the backend adds layers and estimate.
        meta: {
          filename: uploadedFile?.filename,
          material: sliceResult.material,
          slicer_mode: sliceResult.slicerMode,
          layer_height: sliceResult.layerHeight,
          nozzle_diameter: sliceResult.nozzleDiameter,
          infill_pattern: sliceResult.infillPattern,
          infill_density: sliceResult.infillDensity,
        },
      });
      setFeedback(
        r.success
          ? { ok: true, text: t('controls.started', { layers: r.data?.num_layers ?? sliceResult.numLayers }) }
          : { ok: false, text: r.message },
      );
    } catch (e) {
      setFeedback({ ok: false, text: e instanceof ApiError ? e.message : String(e) });
    } finally {
      setStarting(false);
    }
  };

  const handlePause = () => api.post('/print/pause');
  const handleResume = () => api.post('/print/resume');
  const handleCancel = () => api.post('/print/cancel', { retract_and_home: true });
  const handleCalibrate = () => api.post('/calibrate', { use_current_pose: true });

  return (
    <Card>
      <div className="grid grid-cols-2 gap-2">
        <Button
          onClick={handleStart}
          disabled={!canStart}
          disabledReason={startBlockedReason ?? undefined}
          className="col-span-2"
          size="lg"
          aria-busy={starting || undefined}
        >
          {starting ? t('controls.starting') : t('controls.start')}
        </Button>
        <Button
          onClick={handlePause}
          disabled={!canPause}
          disabledReason={t('controls.blocked.notPrinting')}
          variant="secondary"
        >
          {t('controls.pause')}
        </Button>
        <Button
          onClick={handleResume}
          disabled={!canResume}
          disabledReason={t('controls.blocked.notPaused')}
          variant="secondary"
        >
          {t('controls.resume')}
        </Button>
        <Button
          onClick={handleCancel}
          disabled={!canCancel}
          disabledReason={t('controls.blocked.notPrinting')}
          variant="danger"
        >
          {t('controls.cancel')}
        </Button>
        <Button
          onClick={handleCalibrate}
          disabled={calibrateBlockedReason !== null}
          disabledReason={calibrateBlockedReason ?? undefined}
          variant="secondary"
        >
          {t('controls.calibrate')}
        </Button>
      </div>

      {/* State the reason inline as well: a tooltip is invisible on touch,
         and this panel is used from a tablet beside the machine. */}
      {startBlockedReason && !starting && (
        <p className="mt-2 text-xs text-muted">
          {t('controls.blocked.prefix')}: {startBlockedReason}
        </p>
      )}
      {feedback && (
        <p className={`mt-2 text-sm ${feedback.ok ? 'text-ok' : 'text-danger'}`} role="status">
          {feedback.text}
        </p>
      )}
      {state === PrintStateEnum.ERROR && printState.error_message && (
        <p className="mt-2 text-sm text-danger">
          {printState.error_message}
        </p>
      )}
    </Card>
  );
}
