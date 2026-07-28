import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useRobotStore, type RobotModeState } from '../../stores/useRobotStore';
import { useSettingsStore, type RobotModel } from '../../stores/useSettingsStore';
import { api, ApiError } from '../../lib/api';
import { tcpPose } from '../../lib/ur7eFk';
import { GENERIC_UP_POSE } from '../../lib/robotPoses';
import Card from '../common/Card';
import Button from '../common/Button';
import RobotJogViewer from './RobotJogViewer';

/** Full-page robot commissioning view: configuration, status, control
 *  services and manual test. Write endpoints are gated by
 *  ENABLE_TEST_PANEL on the backend; the page itself is always reachable
 *  so status and configuration stay available read-only. */

const ROBOT_MODELS: { value: RobotModel; label: string }[] = [
  { value: 'ur3e', label: 'UR3e' },
  { value: 'ur5e', label: 'UR5e' },
  { value: 'ur7e', label: 'UR7e' },
  { value: 'ur10e', label: 'UR10e' },
  { value: 'ur16e', label: 'UR16e' },
  { value: 'ur20', label: 'UR20' },
  { value: 'ur30', label: 'UR30' },
];

const JOINT_LABELS = [
  'Shoulder Pan',
  'Shoulder Lift',
  'Elbow',
  'Wrist 1',
  'Wrist 2',
  'Wrist 3',
];

const JOG_DEGREES = [-5, -1, 1, 5];

function rad2deg(r: number): number {
  return (r * 180) / Math.PI;
}
function deg2rad(d: number): number {
  return (d * Math.PI) / 180;
}

function ModeBadge({ mode, kind }: { mode: RobotModeState; kind: 'robot' | 'safety' }) {
  // Colour-code by criticality
  const isOK =
    kind === 'safety'
      ? mode.mode_name === 'NORMAL'
      : ['IDLE', 'RUNNING', 'POWER_ON'].includes(mode.mode_name);
  const isBad =
    kind === 'safety'
      ? [
          'PROTECTIVE_STOP',
          'SAFEGUARD_STOP',
          'SYSTEM_EMERGENCY_STOP',
          'ROBOT_EMERGENCY_STOP',
          'VIOLATION',
          'FAULT',
        ].includes(mode.mode_name)
      : ['DISCONNECTED', 'NO_CONTROLLER'].includes(mode.mode_name);

  const colour = isOK
    ? 'bg-green-600 text-white'
    : isBad
    ? 'bg-red-600 text-white'
    : 'bg-yellow-600 text-white';

  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${colour}`}>
      {mode.mode_name}
    </span>
  );
}

export default function RobotPage() {
  const { t } = useTranslation();
  const joints = useRobotStore((s) => s.jointStates.positions);
  const connected = useRobotStore((s) => s.robotConnected);
  const robotMode = useRobotStore((s) => s.robotMode);
  const safetyMode = useRobotStore((s) => s.safetyMode);
  const motionAllowed = useRobotStore((s) => s.motionAllowed);
  const testPanelEnabled = useRobotStore((s) => s.testPanelEnabled);
  const system = useRobotStore((s) => s.system);
  const backendUrType = useRobotStore((s) => s.urType);
  const robotModel = useSettingsStore((s) => s.robotModel);
  const setRobotModel = useSettingsStore((s) => s.setRobotModel);
  const splitView = useSettingsStore((s) => s.robotSplitView);
  const setSplitView = useSettingsStore((s) => s.setRobotSplitView);

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastMsg, setLastMsg] = useState<string | null>(null);
  // Deliberate opt-in to driving the real robot. Component-local and
  // intentionally NOT persisted: every visit to this page starts in
  // simulation, so reopening the app can never leave the operator already
  // armed without having said so in this session.
  const [liveArmed, setLiveArmed] = useState(false);
  const [bedPoints, setBedPoints] = useState<Record<string, { rad: number[]; deg: number[] }>>({});
  const [bedLimits, setBedLimits] = useState<{ size_mm?: number[] } | null>(null);

  // Local simulated pose for the disconnected/offline rehearsal viewer (see
  // RobotJogViewer below). Independent of the live `joints` from the store
  // — jogging in simulation mode never touches the real robot.
  const [simJoints, setSimJoints] = useState<number[]>(GENERIC_UP_POSE);
  // True once the operator has interacted with the simulation (jog, bed
  // point, or manual sync) -- guards the async home-pose fetch below from
  // clobbering an in-progress simulated pose the user is already rehearsing.
  const simTouchedRef = useRef(false);
  // The real HOME pose (rad) for the configured UR_TYPE, used by the "Move
  // to Home" simulation branch so it targets the exact same pose the real
  // /robot/move_to_home endpoint would dispatch.
  const [homePoseRad, setHomePoseRad] = useState<number[] | null>(null);

  // Load the configurable bed reference points + limits, and the real HOME
  // pose, once (all read-only, always allowed). Robot mode / safety mode /
  // connection / joint states are kept fresh by the app-level
  // useRobotStatusPoll() hook (see App.tsx) — it runs regardless of which
  // page is mounted, so this page just reads the store for those.
  useEffect(() => {
    let alive = true;
    api
      .get<{ points: Record<string, { rad: number[]; deg: number[] }>; limits?: { size_mm?: number[] } }>(
        '/robot/bed_points',
      )
      .then((r) => {
        if (alive) {
          setBedPoints(r.points ?? {});
          setBedLimits(r.limits ?? null);
        }
      })
      .catch(() => {
        /* backend may be momentarily unreachable */
      });
    api
      .get<{ rad: number[] }>('/robot/home_pose')
      .then((r) => {
        if (!alive || r.rad?.length !== 6) return;
        setHomePoseRad(r.rad);
        if (!simTouchedRef.current) {
          setSimJoints(r.rad);
        }
      })
      .catch(() => {
        /* fall back to GENERIC_UP_POSE, already set as the initial value */
      });
    return () => {
      alive = false;
    };
  }, []);

  async function runCommand(path: string, label: string) {
    setBusy(label);
    setError(null);
    setLastMsg(null);
    try {
      const r = await api.post<{ success: boolean; message: string }>(path);
      setLastMsg(`${label}: ${r.message || (r.success ? 'OK' : 'failed')}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  // NOTE on confirmations: arming LIVE is itself an explicit, confirmed
  // act (see armLive), so the individual move handlers below do NOT prompt
  // again. Stacking a second dialog immediately after the arm dialog would
  // just train the operator to click through prompts — confirmation fatigue
  // that makes the gate less effective, not more. One deliberate gate, then
  // the red banner + always-visible E-STOP carry the ongoing warning.

  const doJog = (jointIndex: number, deg: number) => async () => {
    // Simulation branch: purely local, no backend call — nothing physically
    // moves.
    if (!canReallyMove) {
      simTouchedRef.current = true;
      setSimJoints((prev) => {
        const next = [...prev];
        next[jointIndex] = next[jointIndex] + deg2rad(deg);
        return next;
      });
      return;
    }
    setBusy(`jog-${jointIndex}-${deg}`);
    setError(null);
    setLastMsg(null);
    try {
      const r = await api.post<{ success: boolean; message: string }>('/robot/jog', {
        joint_index: jointIndex,
        delta_rad: deg2rad(deg),
        duration_s: 1.0,
      });
      setLastMsg(r.message || 'jog dispatched');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const doHome = async () => {
    if (!canReallyMove) {
      simTouchedRef.current = true;
      setSimJoints(homePoseRad ?? GENERIC_UP_POSE);
      return;
    }
    setBusy('home');
    setError(null);
    setLastMsg(null);
    try {
      const r = await api.post<{ success: boolean; message: string }>('/robot/move_to_home');
      setLastMsg(r.message || 'home dispatched');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  /** Copy the real robot's current pose into the simulation, so a rehearsal
   *  started while disconnected can pick up from where the real robot
   *  actually is once you're back online. Simulation-only affordance. */
  const syncSimFromRobot = () => {
    simTouchedRef.current = true;
    setSimJoints(joints);
  };

  const toggleMotionControl = async () => {
    const enable = !system.motionControlEnabled;
    if (enable) {
      const ok = window.confirm(t('test.confirmEnableMotion'));
      if (!ok) return;
    }
    setBusy('motion_control');
    setError(null);
    setLastMsg(null);
    try {
      const r = await api.post<{ success: boolean; message: string }>(
        '/robot/motion_control',
        { enable },
      );
      setLastMsg(r.message || (enable ? 'enabled' : 'disabled'));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const doGotoBedPoint = (name: string) => async () => {
    if (!canReallyMove) {
      const rad = bedPoints[name]?.rad;
      if (!rad) return;
      simTouchedRef.current = true;
      setSimJoints(rad);
      return;
    }
    setBusy(`bed-${name}`);
    setError(null);
    setLastMsg(null);
    try {
      const r = await api.post<{ success: boolean; message: string }>('/robot/goto_bed_point', {
        point: name,
      });
      setLastMsg(r.message || `goto ${name} dispatched`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const freshAge = system.jointStatesAgeS;
  const dataFresh = freshAge != null && freshAge < 0.5;

  // Live TCP pose from the official UR7e DH forward kinematics.
  const pose = tcpPose(joints);

  // Preconditions that must ALL hold before the real robot can be driven:
  // connected, safety/mode allow motion, AND the motion trajectory
  // controller is actually the active one (system.motionControlEnabled --
  // distinct from motionAllowed, see /robot/status).
  const liveAvailable = connected && motionAllowed && system.motionControlEnabled;
  // Which precondition is blocking, so the UI can say WHY LIVE is
  // unavailable rather than leaving the operator to guess. Ordered from
  // most fundamental to most specific.
  const liveBlockedReason = !connected
    ? t('test.reasonDisconnected')
    : !motionAllowed
    ? t('test.reasonMotionNotAllowed')
    : !system.motionControlEnabled
    ? t('test.reasonMotionControlOff')
    : null;

  // Effective mode: LIVE requires BOTH the preconditions and the operator's
  // explicit arming. Simulation is always available, including fully
  // disconnected.
  const canReallyMove = liveArmed && liveAvailable;
  const displayedJoints = canReallyMove ? joints : simJoints;

  // Fail-safe disarm: if any precondition is lost (connection drops, a
  // protective stop trips, the motion controller is deactivated), fall back
  // to simulation immediately rather than leaving the UI armed against a
  // robot it can no longer command safely. Re-arming is an explicit act
  // again. Declared here, after liveAvailable exists, because the dependency
  // array is evaluated during render.
  useEffect(() => {
    if (liveArmed && !liveAvailable) setLiveArmed(false);
  }, [liveArmed, liveAvailable]);

  const armLive = () => {
    if (!window.confirm(t('test.confirmArmLive'))) return;
    setLiveArmed(true);
  };

  const modeSelector = (
    <div
      className={`rounded-lg border px-3 py-2 ${
        canReallyMove
          ? 'border-red-500/50 bg-red-500/10'
          : 'border-blue-500/40 bg-blue-500/10'
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="inline-flex rounded-md bg-gray-200/60 dark:bg-gray-800/60 p-0.5 gap-0.5">
          <button
            onClick={() => setLiveArmed(false)}
            className={`rounded px-3 py-1 text-xs font-semibold transition-colors ${
              !liveArmed
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
            }`}
          >
            {t('test.modeSim')}
          </button>
          <button
            onClick={armLive}
            disabled={!liveAvailable}
            title={liveBlockedReason ?? undefined}
            className={`rounded px-3 py-1 text-xs font-semibold transition-colors ${
              liveArmed
                ? 'bg-red-600 text-white shadow-sm'
                : liveAvailable
                ? 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
                : 'text-gray-400 dark:text-gray-600 cursor-not-allowed'
            }`}
          >
            {t('test.modeLiveRobot')}
          </button>
        </div>
        {!liveArmed && connected && (
          <button
            onClick={syncSimFromRobot}
            className="shrink-0 rounded-md border border-blue-500/50 px-2 py-1 text-[11px] font-medium text-blue-600 dark:text-blue-400 hover:bg-blue-500/10"
          >
            {t('test.syncFromRobot')}
          </button>
        )}
      </div>
      <p
        className={`mt-1.5 text-[11px] ${
          canReallyMove
            ? 'font-semibold text-red-600 dark:text-red-400'
            : 'text-blue-600 dark:text-blue-400'
        }`}
      >
        {canReallyMove
          ? `⚠ ${t('test.liveModeHint')}`
          : liveBlockedReason
          ? `${t('test.liveBlocked')}: ${liveBlockedReason}`
          : t('test.simulationModeHint')}
      </p>
    </div>
  );

  // ── Panel content, grouped but NOT wrapped in layout-specific containers
  // — the classic grid and the split-view right pane each wrap these
  // fragments with their own column/spacing classes below, so the same
  // Card markup is never duplicated between layouts.
  const column1Content = (
    <>
      <Card title={t('settings.robotModel')} collapsible>
        <div className="grid grid-cols-4 gap-1.5">
          {ROBOT_MODELS.map((m) => (
            <button
              key={m.value}
              onClick={() => setRobotModel(m.value)}
              className={`rounded-lg px-2 py-2 text-sm font-semibold transition-colors ${
                robotModel === m.value
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
        {backendUrType && (
          <p className="mt-2 text-[10px] text-gray-500">
            {t('test.backendUrType')}: <span className="font-mono">{backendUrType}</span>
            {backendUrType.toLowerCase() !== robotModel && (
              <span className="ml-1 text-yellow-500">{t('test.modelMismatch')}</span>
            )}
          </p>
        )}
      </Card>

      <Card title={t('test.status')} collapsible>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="flex flex-col gap-1">
            <span className="text-xs text-gray-500">{t('test.robotMode')}</span>
            <ModeBadge mode={robotMode} kind="robot" />
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-xs text-gray-500">{t('test.safetyMode')}</span>
            <ModeBadge mode={safetyMode} kind="safety" />
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-xs text-gray-500">{t('test.connection')}</span>
            <span className={connected ? 'text-green-500 font-semibold' : 'text-red-500 font-semibold'}>
              {connected ? t('test.connected') : t('test.disconnected')}
            </span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-xs text-gray-500">{t('test.motionAllowed')}</span>
            <span className={motionAllowed ? 'text-green-500 font-semibold' : 'text-yellow-500 font-semibold'}>
              {motionAllowed ? t('test.yes') : t('test.no')}
            </span>
          </div>
        </div>
        <div className="mt-4 border-t border-gray-200 dark:border-gray-700 pt-3">
          <span className="text-xs text-gray-500 mb-2 block">{t('test.jointAngles')}</span>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs font-mono">
            {JOINT_LABELS.map((n, i) => (
              <div key={n} className="flex justify-between">
                <span className="text-gray-500">{n}</span>
                <span>{rad2deg(joints[i] ?? 0).toFixed(1)}°</span>
              </div>
            ))}
          </div>
        </div>
      </Card>

      <Card title={t('test.tcpPose')} collapsible>
        <p className="text-[10px] text-gray-500 mb-1">{t('test.tcpFrame')}</p>
        <div className="grid grid-cols-2 gap-3 text-xs font-mono">
          <div>
            <span className="text-gray-500">{t('test.position')} (m)</span>
            <div>X&nbsp;&nbsp;{pose.pos[0].toFixed(3)}</div>
            <div>Y&nbsp;&nbsp;{pose.pos[1].toFixed(3)}</div>
            <div>Z&nbsp;&nbsp;{pose.pos[2].toFixed(3)}</div>
          </div>
          <div>
            <span className="text-gray-500">{t('test.orientation')} (°)</span>
            <div>R&nbsp;&nbsp;{((pose.rpy[0] * 180) / Math.PI).toFixed(1)}</div>
            <div>P&nbsp;&nbsp;{((pose.rpy[1] * 180) / Math.PI).toFixed(1)}</div>
            <div>Y&nbsp;&nbsp;{((pose.rpy[2] * 180) / Math.PI).toFixed(1)}</div>
          </div>
        </div>
      </Card>
    </>
  );

  const column2Content = (
    <>
      <Card title={t('test.systemStatus')} collapsible>
        <div className="space-y-2 text-sm">
          {/* A — External Control program running */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">{t('test.externalControl')}</span>
            <span className={system.programRunning ? 'text-green-500 font-semibold' : 'text-yellow-500 font-semibold'}>
              {system.programRunning ? t('test.running') : t('test.stopped')}
            </span>
          </div>
          {/* A — joint_states data freshness */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">{t('test.dataStream')}</span>
            <span className={dataFresh ? 'text-green-500 font-mono' : 'text-red-500 font-mono'}>
              {freshAge == null ? '—' : `${freshAge.toFixed(2)} s`}
            </span>
          </div>
          {/* C — motion control enabled + active controller */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">{t('test.motionControl')}</span>
            <span className={system.motionControlEnabled ? 'text-green-500 font-semibold' : 'text-yellow-500 font-semibold'}>
              {system.motionControlEnabled ? t('test.enabled') : t('test.disabled')}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">{t('test.activeController')}</span>
            <span className="text-xs font-mono">{system.activeTrajectoryController}</span>
          </div>
          <Button
            onClick={toggleMotionControl}
            disabled={!connected || busy !== null}
            variant={system.motionControlEnabled ? 'secondary' : 'primary'}
            className="w-full"
          >
            {system.motionControlEnabled ? t('test.disableMotion') : t('test.enableMotion')}
          </Button>

          {/* E — node health */}
          <div className="mt-2 border-t border-gray-200 dark:border-gray-700 pt-2">
            <span className="text-xs text-gray-500 mb-1 block">{t('test.nodeHealth')}</span>
            <div className="grid grid-cols-1 gap-y-1 text-xs">
              {Object.keys(system.nodes).length === 0 && (
                <span className="text-gray-500">—</span>
              )}
              {Object.entries(system.nodes).map(([key, n]) => (
                <div key={key} className="flex items-center justify-between">
                  <span className="text-gray-500">{n.label}</span>
                  <span className={n.alive ? 'text-green-500' : 'text-red-500'}>
                    {n.alive ? '● ' + t('test.alive') : '○ ' + t('test.down')}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Card>

      <Card title={t('test.controlCommands')} collapsible>
        <div className="grid grid-cols-2 gap-2">
          <Button
            onClick={() => runCommand('/robot/power_on', 'power_on')}
            disabled={!connected || busy !== null}
            variant="primary"
          >
            {t('test.powerOn')}
          </Button>
          <Button
            onClick={() => runCommand('/robot/brake_release', 'brake_release')}
            disabled={!connected || busy !== null}
            variant="primary"
          >
            {t('test.brakeRelease')}
          </Button>
          <Button
            onClick={() => runCommand('/robot/play', 'play')}
            disabled={!connected || busy !== null}
            variant="primary"
          >
            {t('test.play')}
          </Button>
          <Button
            onClick={() => runCommand('/robot/stop', 'stop')}
            disabled={busy !== null}
            variant="danger"
          >
            {t('test.stop')}
          </Button>
          <Button
            onClick={() => runCommand('/robot/power_off', 'power_off')}
            disabled={!connected || busy !== null}
            variant="secondary"
            className="col-span-2"
          >
            {t('test.powerOff')}
          </Button>
        </div>
      </Card>
    </>
  );

  const column3Content = (
    <>
      <Card title={t('test.manualJog')} collapsible>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs font-mono mb-3">
          {JOINT_LABELS.map((name, i) => (
            <div key={name} className="flex justify-between">
              <span className="text-gray-500">{name}</span>
              <span>{rad2deg(displayedJoints[i] ?? 0).toFixed(1)}°</span>
            </div>
          ))}
        </div>
        <div className="space-y-2">
          {JOINT_LABELS.map((name, i) => (
            <div key={name} className="grid grid-cols-[1fr_repeat(4,_auto)] gap-1.5 items-center">
              <span className="text-xs text-gray-500">{name}</span>
              {JOG_DEGREES.map((d) => (
                <button
                  key={d}
                  onClick={doJog(i, d)}
                  disabled={busy !== null}
                  className={`px-2 py-1 text-xs font-mono rounded-md border ${
                    busy !== null
                      ? 'border-gray-600 text-gray-600 cursor-not-allowed'
                      : 'border-gray-400 dark:border-gray-600 hover:bg-blue-100 dark:hover:bg-blue-900'
                  }`}
                >
                  {d > 0 ? `+${d}°` : `${d}°`}
                </button>
              ))}
            </div>
          ))}
        </div>
        <Button
          onClick={doHome}
          disabled={busy !== null}
          variant="primary"
          className="w-full mt-3"
        >
          {t('test.moveToHome')}
        </Button>
      </Card>

      <Card title={t('test.bedPoints')} collapsible>
        {bedLimits?.size_mm && (
          <p className="text-[10px] text-gray-500 mb-2">
            {t('test.bedSize')}: {bedLimits.size_mm[0].toFixed(0)} × {bedLimits.size_mm[1].toFixed(0)} mm
          </p>
        )}
        <div className="space-y-1.5">
          {['p1', 'p2', 'p3', 'p4', 'center']
            .filter((k) => bedPoints[k])
            .map((k) => (
              <div key={k} className="grid grid-cols-[auto_1fr_auto] gap-2 items-center">
                <span className="text-xs font-semibold w-14">{k.toUpperCase()}</span>
                <span className="text-[10px] text-gray-500 font-mono truncate">
                  {(bedPoints[k].deg ?? []).map((d) => d.toFixed(0)).join(', ')}°
                </span>
                <button
                  onClick={doGotoBedPoint(k)}
                  disabled={busy !== null}
                  className={`px-2 py-1 text-xs rounded-md border ${
                    busy !== null
                      ? 'border-gray-600 text-gray-600 cursor-not-allowed'
                      : 'border-gray-400 dark:border-gray-600 hover:bg-blue-100 dark:hover:bg-blue-900'
                  }`}
                >
                  {t('test.gotoPoint')}
                </button>
              </div>
            ))}
        </div>
      </Card>
    </>
  );

  // Split-view checkbox toggle — always available regardless of connection
  // / gating state, since it's purely a layout preference. Persisted via
  // useSettingsStore (robotSplitView) so it survives reloads.
  const splitViewToggle = (
    <label className="inline-flex items-center gap-2 cursor-pointer select-none text-sm font-medium text-gray-700 dark:text-gray-300">
      <span className="relative inline-flex h-5 w-9 shrink-0 items-center">
        <input
          type="checkbox"
          checked={splitView}
          onChange={(e) => setSplitView(e.target.checked)}
          className="peer sr-only"
        />
        <span className="absolute inset-0 rounded-full bg-gray-300 dark:bg-gray-700 peer-checked:bg-blue-600 transition-colors" />
        <span className="absolute left-0.5 h-4 w-4 rounded-full bg-white transition-transform peer-checked:translate-x-4" />
      </span>
      {t('test.splitView')}
    </label>
  );

  return (
    <div className="flex-1 min-h-0 flex flex-col overflow-hidden bg-gray-50 dark:bg-gray-950">
      <div className="flex-shrink-0 p-4 pb-0 space-y-3">
        <div className="flex items-center justify-end">
          {splitViewToggle}
        </div>

        {!testPanelEnabled && (
          <div className="rounded-lg border border-yellow-500/40 bg-yellow-500/10 px-4 py-2 text-sm text-yellow-600 dark:text-yellow-400">
            {t('test.panelDisabled')}
          </div>
        )}
        {(lastMsg || error || busy) && (
          <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-4 py-2 text-sm">
            {busy && <span className="text-gray-500">⏳ {busy}…</span>}
            {lastMsg && !error && <span className="text-green-500">✓ {lastMsg}</span>}
            {error && <span className="text-red-500">✗ {error}</span>}
          </div>
        )}

        {!splitView && modeSelector}
      </div>

      {splitView ? (
        /* ── Split layout: left = live/simulated robot view, right =
           panels stacked in a single scrollable column. Reuses the exact
           same scene (RobotJogViewer) as the Printer > Live camera/scale. */
        <div className="flex-1 min-h-0 flex overflow-hidden">
          <div className="w-1/2 h-full border-r border-gray-200 dark:border-gray-800 flex-shrink-0">
            <RobotJogViewer joints={displayedJoints} />
          </div>
          <div className="w-1/2 overflow-y-auto p-4">
            <div className="mx-auto max-w-2xl space-y-4">
              {modeSelector}
              {column1Content}
              {column2Content}
              {column3Content}
            </div>
          </div>
        </div>
      ) : (
        /* ── Classic layout: no 3D view, panels in a 3-column grid. */
        <div className="flex-1 min-h-0 overflow-y-auto p-4">
          <div className="mx-auto max-w-7xl">
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 items-start">
              <div className="space-y-4">{column1Content}</div>
              <div className="space-y-4">{column2Content}</div>
              <div className="space-y-4 md:col-span-2 xl:col-span-1">{column3Content}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
