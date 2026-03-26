/**
 * Placeholder RobotModel component.
 * Full URDF loading requires urdf-loader + mesh conversion at Docker build time.
 * For now, renders a simple representation of the UR arm base.
 */
import { useRobotStore } from '../../stores/useRobotStore';

export default function RobotModel() {
  const connected = useRobotStore((s) => s.connected);

  if (!connected) return null;

  // Placeholder — a simple cylinder representing the robot base
  return (
    <group position={[0, 0, 0]}>
      <mesh position={[0, 0.05, 0]}>
        <cylinderGeometry args={[0.075, 0.075, 0.1, 32]} />
        <meshStandardMaterial color="#4b5563" />
      </mesh>
    </group>
  );
}
