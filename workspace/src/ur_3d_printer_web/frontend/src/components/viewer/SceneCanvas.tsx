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

const CAMERA_PRESETS = {
  iso: { position: new THREE.Vector3(150, 120, 150), target: new THREE.Vector3(0, 30, 0) },
  top: { position: new THREE.Vector3(0, 200, 0), target: new THREE.Vector3(0, 0, 0) },
  front: { position: new THREE.Vector3(0, 50, 200), target: new THREE.Vector3(0, 30, 0) },
};

export default function SceneCanvas() {
  const theme = useSettingsStore((s) => s.theme);
  const controlsRef = useRef<OrbitControlsImpl>(null);

  const isDark =
    theme === 'dark' ||
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

  const bgColor = isDark ? '#1a1a2e' : '#f0f0f0';

  const handleCameraPreset = useCallback((preset: 'top' | 'front' | 'iso') => {
    const cam = CAMERA_PRESETS[preset];
    if (controlsRef.current) {
      controlsRef.current.object.position.copy(cam.position);
      controlsRef.current.target.copy(cam.target);
      controlsRef.current.update();
    }
  }, []);

  return (
    <div className="relative w-full h-full min-h-[300px]">
      <Canvas
        camera={{ position: [150, 120, 150], fov: 50, near: 0.1, far: 2000 }}
        style={{ background: bgColor }}
        onPointerMissed={() => usePrintStore.getState().setObjectSelected(false)}
      >
        <ambientLight intensity={0.4} />
        <directionalLight position={[100, 200, 100]} intensity={0.8} />
        <directionalLight position={[-100, 100, -100]} intensity={0.3} />
        <PrintBed />
        <StlPreview />
        <Toolpath />
        <RobotModel />
        <OrbitControls ref={controlsRef} makeDefault />
      </Canvas>
      <ObjectTools />
      <LayerSlider />
      <ViewerControls onCameraPreset={handleCameraPreset} />
    </div>
  );
}
