import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useRobotStore, type RobotModeState } from '../../stores/useRobotStore';
import { api, ApiError } from '../../lib/api';
import { tcpPose } from '../../lib/ur7eFk';
import Card from '../common/Card';
import Button from '../common/Button';

/** Bring-up / commissioning panel. Gated by ENABLE_TEST_PANEL on the
 *  backend; this component renders only when /api/health reports it as on. */

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

export default function TestPanel() {
  const { t } = useTranslation();
  const joints = useRobotStore((s) => s.jointStates.positions);
  const connected = useRobotStore((s) => s.connected);
  const robotMode = useRobotStore((s) => s.robotMode);
  const safetyMode = useRobotStore((s) => s.safetyMode);
  const motionAllowed = useRobotStore((s) => s.motionAllowed);
  const system = useRobotStore((s) => s.system);

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastMsg, setLastMsg] = useState<string | null>(null);
  const [confirmedMotion, setConfirmedMotion] = useState(false);
  const [bedPoints, setBedPoints] = useState<Record<string, { deg: number[] }>>({});
  const [bedLimits, setBedLimits] = useState<{ size_mm?: number[] } | null>(null);

  // Load the configurable bed reference points + limits once (read-only).
  useEffect(() => {
    let alive = true;
    api
      .get<{ points: Record<string, { deg: number[] }>; limits?: { size_mm?: number[] } }>('/robot/bed_points')
      .then((r) => {
        if (alive) {
          setBedPoints(r.points ?? {});
          setBedLimits(r.limits ?? null);
        }
      })
      .catch(() => {
        /* backend may be momentarily unreachable */
      });
    return () => {
      alive = false;
    };
  }, []);

  // Poll /api/robot/status every 1 s so robotMode/safetyMode stay fresh even
  // before the websocket stream has covered them.
  useEffect(() => {
    let alive = true;
    async function tick() {
      try {
        const s = await api.get<{
          ros2_connected: boolean;
          joint_states: { positions: number[] };
          robot_mode: RobotModeState;
          safety_mode: RobotModeState;
          motion_allowed: boolean;
          test_panel_enabled: boolean;
          program_running: boolean;
          joint_states_age_s: number | null;
          motion_control_enabled: boolean;
          active_trajectory_controller: string;
          nodes: Record<string, { label: string; alive: boolean }>;
        }>('/robot/status');
        if (!alive) return;
        useRobotStore.getState().setRobotMode(s.robot_mode);
        useRobotStore.getState().setSafetyMode(s.safety_mode);
        useRobotStore.getState().setMotionAllowed(s.motion_allowed);
        useRobotStore.getState().setTestPanelEnabled(s.test_panel_enabled);
        useRobotStore.getState().setConnected(s.ros2_connected);
        useRobotStore.getState().setSystem({
          programRunning: s.program_running,
          jointStatesAgeS: s.joint_states_age_s,
          motionControlEnabled: s.motion_control_enabled,
          activeTrajectoryController: s.active_trajectory_controller,
          nodes: s.nodes ?? {},
        });
        if (s.joint_states?.positions?.length === 6) {
          useRobotStore.getState().setJointStates({ positions: s.joint_states.positions });
        }
      } catch {
        // Silent — backend may be momentarily unreachable.
      }
    }
    tick();
    const id = window.setInterval(tick, 1000);
    return () => {
      alive = false;
      window.clearInterval(id);
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

  const doJog = (jointIndex: number, deg: number) => async () => {
    if (!confirmedMotion) {
      const ok = window.confirm(
        t('test.confirmMotion', { action: `${JOINT_LABELS[jointIndex]} ${deg > 0 ? '+' : ''}${deg}°` }),
      );
      if (!ok) return;
      setConfirmedMotion(true);
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
    if (!confirmedMotion) {
      const ok = window.confirm(t('test.confirmMotion', { action: 'Move to Home' }));
      if (!ok) return;
      setConfirmedMotion(true);
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
    const ok = window.confirm(t('test.confirmMotion', { action: `${t('test.bedPoint')} ${name.toUpperCase()}` }));
    if (!ok) return;
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

  const motionDisabled = !motionAllowed || !connected;

  return (
    <div className="space-y-4">
      {/* ── Status ────────────────────────────────────────────── */}
      <Card title={t('test.status')}>
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

      {/* ── Live TCP pose (UR7e DH forward kinematics) ────────── */}
      <Card title={t('test.tcpPose')}>
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

      {/* ── System / control states (A · C · E) ───────────────── */}
      <Card title={t('test.systemStatus')}>
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

      {/* ── Dashboard commands ────────────────────────────────── */}
      <Card title={t('test.controlCommands')}>
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

      {/* ── Manual jog ────────────────────────────────────────── */}
      <Card title={t('test.manualJog')}>
        {!motionAllowed && (
          <p className="text-xs text-yellow-500 mb-2">{t('test.motionBlocked')}</p>
        )}
        <div className="space-y-2">
          {JOINT_LABELS.map((name, i) => (
            <div key={name} className="grid grid-cols-[1fr_repeat(4,_auto)] gap-1.5 items-center">
              <span className="text-xs text-gray-500">{name}</span>
              {JOG_DEGREES.map((d) => (
                <button
                  key={d}
                  onClick={doJog(i, d)}
                  disabled={motionDisabled || busy !== null}
                  className={`px-2 py-1 text-xs font-mono rounded-md border ${
                    motionDisabled
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
          disabled={motionDisabled || busy !== null}
          variant="primary"
          className="w-full mt-3"
        >
          {t('test.moveToHome')}
        </Button>
      </Card>

      {/* ── Test print-bed reference points ───────────────────── */}
      <Card title={t('test.bedPoints')}>
        {bedLimits?.size_mm && (
          <p className="text-[10px] text-gray-500 mb-2">
            {t('test.bedSize')}: {bedLimits.size_mm[0].toFixed(0)} × {bedLimits.size_mm[1].toFixed(0)} mm
          </p>
        )}
        {!system.motionControlEnabled && (
          <p className="text-xs text-yellow-500 mb-2">{t('test.enableMotionFirst')}</p>
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
                  disabled={motionDisabled || busy !== null || !system.motionControlEnabled}
                  className={`px-2 py-1 text-xs rounded-md border ${
                    motionDisabled || !system.motionControlEnabled
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

      {/* ── Feedback area ─────────────────────────────────────── */}
      {(lastMsg || error || busy) && (
        <Card>
          {busy && <p className="text-xs text-gray-500">⏳ {busy}…</p>}
          {lastMsg && !error && <p className="text-xs text-green-500">✓ {lastMsg}</p>}
          {error && <p className="text-xs text-red-500">✗ {error}</p>}
        </Card>
      )}
    </div>
  );
}
