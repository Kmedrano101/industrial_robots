import { useEffect, useRef, useState } from 'react';
import { useFrame } from '@react-three/fiber';
import { useRobotStore } from '../../stores/useRobotStore';
import { useSettingsStore } from '../../stores/useSettingsStore';
import URDFLoader from 'urdf-loader';
import { ColladaLoader } from 'three/addons/loaders/ColladaLoader.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import * as THREE from 'three';
import type { URDFRobot } from 'urdf-loader';

const JOINT_NAMES = [
  'shoulder_pan_joint',
  'shoulder_lift_joint',
  'elbow_joint',
  'wrist_1_joint',
  'wrist_2_joint',
  'wrist_3_joint',
];

/** Normalize angle to (-pi, pi] — prefer +pi over -pi. */
function normalizeAngle(angle: number): number {
  let n = Math.atan2(Math.sin(angle), Math.cos(angle));
  // atan2 returns -pi for both -pi and +pi; prefer +pi
  if (n <= -Math.PI + 1e-6) n = Math.PI;
  return n;
}

export default function RobotModel() {
  const [robot, setRobot] = useState<URDFRobot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const groupRef = useRef<THREE.Group>(null);
  const loggedRef = useRef(false);
  const jointPositions = useRobotStore((s) => s.jointStates.positions);
  const robotModel = useSettingsStore((s) => s.robotModel);

  useEffect(() => {
    setRobot(null);
    setError(null);
    loggedRef.current = false;

    fetch(`/robots/${robotModel}.urdf`)
      .then((res) => {
        if (!res.ok) throw new Error(`URDF fetch failed: ${res.status}`);
        return res.text();
      })
      .then((urdfText) => {
        const loader = new URDFLoader();
        loader.parseCollision = false;
        loader.parseVisual = true;
        loader.workingPath = '/';

        loader.loadMeshCb = (url, manager, onLoad) => {
          const cleanUrl = url.replace(/\/+/g, '/');
          if (cleanUrl.endsWith('.dae')) {
            const colladaLoader = new ColladaLoader(manager);
            colladaLoader.load(cleanUrl, (result) => {
              onLoad(result.scene);
            }, undefined, () => {
              onLoad(new THREE.Object3D());
            });
          } else if (cleanUrl.endsWith('.stl')) {
            const stlLoader = new STLLoader(manager);
            stlLoader.load(cleanUrl, (geo) => {
              const mat = new THREE.MeshStandardMaterial({ color: 0x888888, metalness: 0.4, roughness: 0.6 });
              onLoad(new THREE.Mesh(geo, mat));
            }, undefined, () => {
              onLoad(new THREE.Object3D());
            });
          } else {
            loader.defaultMeshLoader(cleanUrl, manager, onLoad);
          }
        };

        const parsed = loader.parse(urdfText);

        parsed.traverse((child) => {
          if (child instanceof THREE.Mesh) {
            child.castShadow = true;
            child.receiveShadow = true;
          }
        });

        // Disable joint limits — we normalize angles ourselves
        Object.values(parsed.joints).forEach((joint) => {
          joint.ignoreLimits = true;
        });

        // Set initial home pose (nozzle pointing down at bed)
        parsed.setJointValue('shoulder_pan_joint', Math.PI);
        parsed.setJointValue('shoulder_lift_joint', -Math.PI / 2);
        parsed.setJointValue('elbow_joint', Math.PI / 2);
        parsed.setJointValue('wrist_1_joint', -Math.PI / 2);
        parsed.setJointValue('wrist_2_joint', -Math.PI / 2);
        parsed.setJointValue('wrist_3_joint', 0);

        console.log(`URDF loaded (${robotModel}):`, Object.keys(parsed.joints).length, 'joints,', Object.keys(parsed.links).length, 'links');
        setRobot(parsed);
      })
      .catch((err) => {
        console.error('URDF load error:', err);
        setError(String(err));
      });
  }, [robotModel]);

  // Update joint values from ROS2 at render rate
  useFrame(() => {
    if (!robot || !jointPositions || jointPositions.length < 6) return;
    // Skip if no real data yet (all zeros = store default)
    if (jointPositions.every((v) => v === 0)) return;

    for (let i = 0; i < JOINT_NAMES.length; i++) {
      const normalized = normalizeAngle(jointPositions[i]);
      robot.setJointValue(JOINT_NAMES[i], normalized);
    }

    // Log once for debugging
    if (!loggedRef.current) {
      const raw = jointPositions.map((v) => (v * 180 / Math.PI).toFixed(1));
      const norm = jointPositions.map((v) => (normalizeAngle(v) * 180 / Math.PI).toFixed(1));
      console.log('Joint raw (deg):', raw);
      console.log('Joint normalized (deg):', norm);
      loggedRef.current = true;
    }
  });

  if (error) {
    return (
      <group>
        <mesh position={[0, 0.5, 0]}>
          <boxGeometry args={[0.1, 1, 0.1]} />
          <meshStandardMaterial color="red" />
        </mesh>
      </group>
    );
  }

  if (!robot) return null;

  return (
    <group ref={groupRef} rotation={[-Math.PI / 2, 0, 0]}>
      <primitive object={robot} />
    </group>
  );
}
