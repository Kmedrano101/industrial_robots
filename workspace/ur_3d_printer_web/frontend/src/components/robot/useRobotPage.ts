import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useRobotStore } from '../../stores/useRobotStore';
import { api, ApiError } from '../../lib/api';
import { tcpPose } from '../../lib/ur7eFk';
import { GENERIC_UP_POSE } from '../../lib/robotPoses';
import { JOINT_LABELS, deg2rad, rad2deg } from './robotConstants';

export type BedPoints = Record<string, { rad: number[]; deg: number[] }>;

/**
 * All state and actions behind the Robot page, kept out of the markup so
 * the cards can be small, prop-driven components. Every "move" action has
 * two branches: a purely local simulation when LIVE is not armed, and the
 * real backend call when it is.
 */
export function useRobotPage() {
  const { t } = useTranslation();
  const joints = useRobotStore((s) => s.jointStates.positions);
  const connected = useRobotStore((s) => s.robotConnected);
  const motionAllowed = useRobotStore((s) => s.motionAllowed);
  const system = useRobotStore((s) => s.system);

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastMsg, setLastMsg] = useState<string | null>(null);
  // Deliberate opt-in to driving the real robot. Component-local and
  // intentionally NOT persisted: every visit to this page starts in
  // simulation, so reopening the app can never leave the operator already
  // armed without having said so in this session.
  const [liveArmed, setLiveArmed] = useState(false);
  // Overlay the rehearsed pose on the real one. Only meaningful with a robot
  // attached, and off by default so the viewer stays uncluttered.
  const [compareSim, setCompareSim] = useState(false);
  const [bedPoints, setBedPoints] = useState<BedPoints>({});
  const [bedLimits, setBedLimits] = useState<{ size_mm?: number[] } | null>(null);

  // Local simulated pose for the disconnected/offline rehearsal viewer.
  // Independent of the live `joints` from the store — jogging in
  // simulation mode never touches the real robot.
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
  // pose, once (all read-only, always allowed). Modes / connection / joints
  // come from the store, fed by the WebSocket and the status poll.
  useEffect(() => {
    let alive = true;
    api
      .get<{ points: BedPoints; limits?: { size_mm?: number[] } }>('/robot/bed_points')
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
        if (!simTouchedRef.current) setSimJoints(r.rad);
      })
      .catch(() => {
        /* fall back to GENERIC_UP_POSE, already set as the initial value */
      });
    return () => {
      alive = false;
    };
  }, []);

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

  // Fail-safe disarm: if any precondition is lost (connection drops, a
  // protective stop trips, the motion controller is deactivated), fall back
  // to simulation immediately rather than leaving the UI armed against a
  // robot it can no longer command safely. Re-arming is an explicit act.
  useEffect(() => {
    if (liveArmed && !liveAvailable) setLiveArmed(false);
  }, [liveArmed, liveAvailable]);

  async function post(
    label: string,
    path: string,
    body?: unknown,
    fallbackMsg?: string,
    prefix?: string,
  ) {
    setBusy(label);
    setError(null);
    setLastMsg(null);
    try {
      const r = await api.post<{ success: boolean; message: string }>(path, body);
      const msg = r.message || fallbackMsg || (r.success ? 'OK' : 'failed');
      setLastMsg(prefix ? `${prefix}: ${msg}` : msg);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  /** Dashboard commands (power on, play, stop, ...): the label is echoed in
   *  the feedback line so the operator sees which one answered. */
  const runCommand = (path: string, label: string) =>
    post(label, path, undefined, undefined, label);

  // NOTE on confirmations: arming LIVE is itself an explicit, confirmed
  // act (see armLive), so the individual move handlers below do NOT prompt
  // again. Stacking a second dialog immediately after the arm dialog would
  // just train the operator to click through prompts — confirmation fatigue
  // that makes the gate less effective, not more. One deliberate gate, then
  // the red banner + always-visible E-STOP carry the ongoing warning.

  const jog = (jointIndex: number, deg: number) => {
    if (!canReallyMove) {
      simTouchedRef.current = true;
      setSimJoints((prev) => {
        const next = [...prev];
        next[jointIndex] = next[jointIndex] + deg2rad(deg);
        return next;
      });
      return;
    }
    void post(
      `jog-${jointIndex}-${deg}`,
      '/robot/jog',
      { joint_index: jointIndex, delta_rad: deg2rad(deg), duration_s: 1.0 },
      'jog dispatched',
    );
  };

  const home = () => {
    if (!canReallyMove) {
      simTouchedRef.current = true;
      setSimJoints(homePoseRad ?? GENERIC_UP_POSE);
      return;
    }
    void post('home', '/robot/move_to_home', undefined, 'home dispatched');
  };

  const gotoBedPoint = (name: string) => {
    if (!canReallyMove) {
      const rad = bedPoints[name]?.rad;
      if (!rad) return;
      simTouchedRef.current = true;
      setSimJoints(rad);
      return;
    }
    void post(`bed-${name}`, '/robot/goto_bed_point', { point: name }, `goto ${name} dispatched`);
  };

  /** Copy the real robot's current pose into the simulation, so a rehearsal
   *  started while disconnected can pick up from where the real robot
   *  actually is once you're back online. Simulation-only affordance. */
  const syncSimFromRobot = () => {
    simTouchedRef.current = true;
    setSimJoints(joints);
  };

  const toggleMotionControl = () => {
    const enable = !system.motionControlEnabled;
    if (enable && !window.confirm(t('test.confirmEnableMotion'))) return;
    void post('motion_control', '/robot/motion_control', { enable }, enable ? 'enabled' : 'disabled');
  };

  const armLive = () => {
    if (!window.confirm(t('test.confirmArmLive'))) return;
    setLiveArmed(true);
  };
  const disarmLive = () => setLiveArmed(false);

  const displayedJoints = canReallyMove ? joints : simJoints;
  // The overlay only says something when there are two genuinely different
  // sources: the real arm and the rehearsed pose. Without a robot both would
  // be the simulation and the ghost would sit exactly on top, implying an
  // agreement that was never measured.
  const canCompare = connected && simTouchedRef.current;
  const comparing = compareSim && canCompare;
  const ghostJoints = comparing ? simJoints : undefined;
  // While comparing, the solid arm is always the REAL one — otherwise, when
  // not armed, displayedJoints is also the simulation and the two bodies
  // coincide exactly, showing a single arm and implying zero deviation while
  // the readout says otherwise.
  const viewerJoints = comparing ? joints : displayedJoints;
  const jointDeviationsDeg = JOINT_LABELS.map((_, i) =>
    rad2deg((joints[i] ?? 0) - (simJoints[i] ?? 0)),
  );
  const maxDeviationDeg = Math.max(...jointDeviationsDeg.map(Math.abs));

  return {
    // store-derived
    joints,
    connected,
    motionAllowed,
    system,
    // live TCP pose from the official UR7e DH forward kinematics
    pose: tcpPose(joints),
    // feedback
    busy,
    error,
    lastMsg,
    // live / simulation
    liveArmed,
    liveAvailable,
    liveBlockedReason,
    canReallyMove,
    armLive,
    disarmLive,
    displayedJoints,
    viewerJoints,
    ghostJoints,
    // compare
    compareSim,
    setCompareSim,
    canCompare,
    jointDeviationsDeg,
    maxDeviationDeg,
    // bed
    bedPoints,
    bedLimits,
    // actions
    runCommand,
    jog,
    home,
    gotoBedPoint,
    syncSimFromRobot,
    toggleMotionControl,
  };
}

export type RobotPageController = ReturnType<typeof useRobotPage>;
