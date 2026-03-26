import * as THREE from 'three';

export default function PrintBed() {
  return (
    <group>
      {/* Grid on the XZ plane (flat on the floor) */}
      <gridHelper args={[200, 20, '#374151', '#1f2937']} position={[0, 0, 0]} />

      {/* Bed surface */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.05, 0]} receiveShadow>
        <planeGeometry args={[200, 200]} />
        <meshStandardMaterial
          color="#1f2937"
          opacity={0.4}
          transparent
          side={THREE.DoubleSide}
        />
      </mesh>
    </group>
  );
}
