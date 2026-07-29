import { useEffect, useRef } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import { useTranslation } from 'react-i18next';
import {
  useSettingsStore,
  DEFAULT_ROBOT_CAMERA_VIEW,
  type CameraView,
} from '../../stores/useSettingsStore';
import { viewerBackground } from '../../lib/theme';
import RobotModel from '../viewer/RobotModel';

interface RobotJogViewerProps {
  /** Joint angles (rad) to render — either the live robot's actual pose or
   *  a local simulated one, decided by the caller (see RobotPage). */
  joints: number[];
  /** Optional second pose drawn as a translucent overlay, for seeing how far
   *  the real arm sits from the rehearsed one. Omitted when not comparing. */
  ghostJoints?: number[];
}

/** Applies the persisted camera pose once the OrbitControls instance exists.
 *  Lives inside <Canvas> because it needs useThree(); `makeDefault` on the
 *  controls below is what publishes them to useThree().controls. */
function RestoreCameraView() {
  const { camera, controls } = useThree();

  useEffect(() => {
    const orbit = controls as OrbitControlsImpl | null;
    if (!orbit) return;
    const view = useSettingsStore.getState().robotCameraView ?? DEFAULT_ROBOT_CAMERA_VIEW;
    camera.position.set(...view.position);
    orbit.target.set(...view.target);
    orbit.update();
    // Runs once per mount (and again if the controls instance is recreated),
    // deliberately NOT on every robotCameraView change — otherwise saving
    // the view while orbiting would fight the user's own drag.
  }, [controls, camera]);

  return null;
}

/** Standalone 3D viewer reusing the same lighting/scale/scene content as
 *  SceneCanvas's "Live" mode (meter-scale URDF + grid + table surface),
 *  minus the printer-specific content (STL preview, toolpath, layer slider)
 *  since this page is about the robot alone.
 *
 *  Camera framing is persisted: whatever view the operator leaves it in is
 *  restored on the next load, so a working viewpoint doesn't have to be
 *  re-found after every reload. */
export default function RobotJogViewer({ joints, ghostJoints }: RobotJogViewerProps) {
  const { t } = useTranslation();
  const theme = useSettingsStore((s) => s.theme);
  const setCameraView = useSettingsStore((s) => s.setRobotCameraView);
  const controlsRef = useRef<OrbitControlsImpl>(null);
  // Read once for the Canvas's initial camera prop; subsequent restores are
  // handled by RestoreCameraView so this doesn't need to be reactive.
  const initial = useSettingsStore.getState().robotCameraView ?? DEFAULT_ROBOT_CAMERA_VIEW;

  /** Persist on interaction end rather than on every change: OrbitControls
   *  fires 'change' continuously while dragging, which would write to
   *  localStorage dozens of times per second. */
  const handleEnd = () => {
    const orbit = controlsRef.current;
    if (!orbit) return;
    const p = orbit.object.position;
    const tg = orbit.target;
    setCameraView({
      position: [p.x, p.y, p.z],
      target: [tg.x, tg.y, tg.z],
    } satisfies CameraView);
  };

  /** Clear the saved view AND snap the live camera back, so the button acts
   *  immediately instead of only taking effect on the next reload. */
  const resetView = () => {
    setCameraView(null);
    const orbit = controlsRef.current;
    if (!orbit) return;
    orbit.object.position.set(...DEFAULT_ROBOT_CAMERA_VIEW.position);
    orbit.target.set(...DEFAULT_ROBOT_CAMERA_VIEW.target);
    orbit.update();
  };

  return (
    <div className="relative w-full h-full">
      <Canvas
        camera={{ position: initial.position, fov: 50, near: 0.01, far: 50 }}
        style={{ background: viewerBackground(theme) }}
      >
        <ambientLight intensity={0.5} />
        <directionalLight position={[3, 5, 3]} intensity={0.8} castShadow />
        <directionalLight position={[-3, 3, -3]} intensity={0.3} />
        <RobotModel joints={joints} />
        {ghostJoints && <RobotModel joints={ghostJoints} ghost />}
        {/* Grid at table surface height (0.9m in URDF Z = 0.9m in Three.js Y
           after rotation) + the table surface itself — matches SceneCanvas's
           Live mode exactly. */}
        <gridHelper args={[4, 20, '#374151', '#1f2937']} position={[0, 0.9, 0]} />
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.898, 0]} receiveShadow>
          <planeGeometry args={[1.2, 0.8]} />
          <meshStandardMaterial color="#374151" opacity={0.5} transparent />
        </mesh>
        <OrbitControls ref={controlsRef} makeDefault onEnd={handleEnd} />
        <RestoreCameraView />
      </Canvas>

      {/* Escape hatch: because the view is persisted, an operator who orbits
         away until the robot is off-screen would otherwise get that same
         useless framing back on every reload. */}
      <button
        onClick={resetView}
        title={t('viewer.resetViewHint')}
        className="absolute top-2 right-2 z-10 rounded-md bg-black/50 backdrop-blur-sm border border-white/15 px-2 py-1 text-[11px] font-medium text-gray-200 hover:bg-black/70 transition-colors"
      >
        {t('viewer.reset')}
      </button>
    </div>
  );
}
