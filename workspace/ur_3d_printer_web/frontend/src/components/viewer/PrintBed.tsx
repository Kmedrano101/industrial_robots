import * as THREE from 'three';
import { useSettingsStore } from '../../stores/useSettingsStore';
import { viewerGrid } from '../../lib/theme';

export default function PrintBed() {
  const theme = useSettingsStore((s) => s.theme);
  const grid = viewerGrid(theme);
  return (
    <group>
      {/* Grid on the XZ plane (flat on the floor) */}
      <gridHelper args={[200, 20, grid.major, grid.minor]} position={[0, 0, 0]} />

      {/* Bed surface */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.05, 0]} receiveShadow>
        <planeGeometry args={[200, 200]} />
        <meshStandardMaterial
          color={grid.bed}
          opacity={0.4}
          transparent
          side={THREE.DoubleSide}
        />
      </mesh>
    </group>
  );
}
