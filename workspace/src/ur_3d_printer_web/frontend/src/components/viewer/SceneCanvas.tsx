import { useRef, useCallback } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import * as THREE from 'three';
import { useSettingsStore } from '../../stores/useSettingsStore';
import { usePrintStore } from '../../stores/usePrintStore';
import PrintBed from './PrintBed';
import StlPreview from './StlPreview';
import Toolpath from './Toolpath';
import RobotModel from './RobotModel';
import LayerSlider from './LayerSlider';
import ViewerControls from './ViewerControls';
import ObjectTools from './ObjectTools';
import ViewModeToggle from './ViewModeToggle';

// Prepare mode: mm scale (STL objects are 10-200mm)
const PREPARE_CONFIG = {
  camera: { position: [150, 120, 150] as [number, number, number], fov: 50, near: 0.1, far: 2000 },
  presets: {
    iso: { position: new THREE.Vector3(150, 120, 150), target: new THREE.Vector3(0, 30, 0) },
    top: { position: new THREE.Vector3(0, 200, 0), target: new THREE.Vector3(0, 0, 0) },
    front: { position: new THREE.Vector3(0, 50, 200), target: new THREE.Vector3(0, 30, 0) },
  },
  lights: {
    dir1: [100, 200, 100] as [number, number, number],
    dir2: [-100, 100, -100] as [number, number, number],
  },
};

// Live mode: meter scale (URDF robot is ~1m tall)
const LIVE_CONFIG = {
  camera: { position: [1.5, 1.5, 1.5] as [number, number, number], fov: 50, near: 0.01, far: 50 },
  presets: {
    iso: { position: new THREE.Vector3(1.5, 1.5, 1.5), target: new THREE.Vector3(0, 0.7, 0) },
    top: { position: new THREE.Vector3(0, 3.0, 0.01), target: new THREE.Vector3(0, 0.7, 0) },
    front: { position: new THREE.Vector3(0, 1.0, 2.0), target: new THREE.Vector3(0, 0.7, 0) },
  },
  lights: {
    dir1: [3, 5, 3] as [number, number, number],
    dir2: [-3, 3, -3] as [number, number, number],
  },
};

export default function SceneCanvas() {
  const theme = useSettingsStore((s) => s.theme);
  const viewMode = useSettingsStore((s) => s.viewMode);
  const controlsRef = useRef<OrbitControlsImpl>(null);

  const isDark =
    theme === 'dark' ||
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

  const bgColor = isDark ? '#1a1a2e' : '#f0f0f0';
  const isLive = viewMode === 'live';
  const config = isLive ? LIVE_CONFIG : PREPARE_CONFIG;

  const handleCameraPreset = useCallback((preset: 'top' | 'front' | 'iso') => {
    const cam = config.presets[preset];
    if (controlsRef.current) {
      controlsRef.current.object.position.copy(cam.position);
      controlsRef.current.target.copy(cam.target);
      controlsRef.current.update();
    }
  }, [config]);

  return (
    <div className="relative w-full h-full min-h-[300px]">
      {/* key forces Canvas remount when switching modes (different camera/scale) */}
      <Canvas
        key={viewMode}
        camera={{ position: config.camera.position, fov: config.camera.fov, near: config.camera.near, far: config.camera.far }}
        style={{ background: bgColor }}
        onPointerMissed={() => usePrintStore.getState().setObjectSelected(false)}
      >
        <ambientLight intensity={0.5} />
        <directionalLight position={config.lights.dir1} intensity={0.8} castShadow />
        <directionalLight position={config.lights.dir2} intensity={0.3} />

        {isLive ? (
          <>
            <RobotModel />
            {/* Floor grid */}
            <gridHelper args={[4, 20, '#374151', '#1f2937']} position={[0, 0, 0]} />
            {/* Table surface (URDF robot mounts at Z=0.9m = Y=0.9 in Three.js) */}
            <mesh rotation={[-Math.PI / 2, 0, 0]} position={[-0.15, 0.875, 0]} receiveShadow>
              <boxGeometry args={[1.2, 0.8, 0.05]} />
              <meshStandardMaterial color="#4b5563" metalness={0.3} roughness={0.7} />
            </mesh>
            {/* Table legs */}
            {[[-0.55, -0.35], [-0.55, 0.35], [0.25, -0.35], [0.25, 0.35]].map(([x, z], i) => (
              <mesh key={i} position={[x, 0.44, z]}>
                <boxGeometry args={[0.06, 0.88, 0.06]} />
                <meshStandardMaterial color="#374151" />
              </mesh>
            ))}
          </>
        ) : (
          <>
            <PrintBed />
            <StlPreview />
            <Toolpath />
          </>
        )}

        <OrbitControls ref={controlsRef} makeDefault />
      </Canvas>

      {/* Overlays */}
      <ViewModeToggle />

      {!isLive && (
        <>
          <ObjectTools />
          <LayerSlider />
        </>
      )}

      <ViewerControls onCameraPreset={handleCameraPreset} />
    </div>
  );
}
