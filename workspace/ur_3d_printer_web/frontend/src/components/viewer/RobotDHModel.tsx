import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { useRobotStore } from '../../stores/useRobotStore';
import { fkFrames } from '../../lib/ur7eFk';

/**
 * Live UR7e visualization built from the official DH parameters (NOT meshes).
 * Renders joint origins (spheres), links (cylinders) and a coordinate triad
 * at the TCP (tool0) showing orientation. Driven by live /joint_states.
 *
 * Works in base_link coordinates (Z up); the parent group in SceneCanvas
 * applies the Z-up -> Three.js Y-up rotation.
 */
const UP = new THREE.Vector3(0, 1, 0);

export default function RobotDHModel() {
  const jointPositions = useRobotStore((s) => s.jointStates.positions);
  const jointRefs = useRef<(THREE.Mesh | null)[]>([]); // base + 6 origins
  const linkRefs = useRef<(THREE.Mesh | null)[]>([]); // 6 link cylinders
  const tcpRef = useRef<THREE.Group>(null);

  useFrame(() => {
    const q = jointPositions;
    if (!q || q.length < 6) return;

    const frames = fkFrames(q);
    const origins = frames.map((m) => new THREE.Vector3().setFromMatrixPosition(m));

    // Joint origin markers (base + 6).
    for (let i = 0; i < origins.length; i++) {
      const mk = jointRefs.current[i];
      if (mk) mk.position.copy(origins[i]);
    }

    // Link cylinders between consecutive origins.
    for (let i = 0; i < 6; i++) {
      const cyl = linkRefs.current[i];
      if (!cyl) continue;
      const a = origins[i];
      const b = origins[i + 1];
      const dir = new THREE.Vector3().subVectors(b, a);
      const len = dir.length();
      cyl.position.copy(a).addScaledVector(dir, 0.5);
      cyl.scale.set(1, Math.max(len, 1e-4), 1);
      if (len > 1e-6) cyl.quaternion.setFromUnitVectors(UP, dir.clone().normalize());
    }

    // TCP frame triad: tool0 transform.
    if (tcpRef.current) {
      tcpRef.current.matrixAutoUpdate = false;
      tcpRef.current.matrix.copy(frames[6]);
    }
  });

  return (
    <group>
      {Array.from({ length: 7 }).map((_, i) => (
        <mesh
          key={`j${i}`}
          ref={(el) => {
            jointRefs.current[i] = el;
          }}
        >
          <sphereGeometry args={[i === 0 ? 0.045 : 0.032, 16, 16]} />
          <meshStandardMaterial color={i === 0 ? '#475569' : '#2563eb'} metalness={0.3} roughness={0.5} />
        </mesh>
      ))}

      {Array.from({ length: 6 }).map((_, i) => (
        <mesh
          key={`l${i}`}
          ref={(el) => {
            linkRefs.current[i] = el;
          }}
        >
          <cylinderGeometry args={[0.022, 0.022, 1, 16]} />
          <meshStandardMaterial color="#9ca3af" metalness={0.4} roughness={0.6} />
        </mesh>
      ))}

      {/* TCP coordinate triad (X red, Y green, Z blue) — orientation. */}
      <group ref={tcpRef}>
        <axesHelper args={[0.15]} />
      </group>
    </group>
  );
}
