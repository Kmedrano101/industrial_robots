import { useEffect, useRef, useState } from 'react';
import { useFrame } from '@react-three/fiber';
import { useRobotStore } from '../../stores/useRobotStore';
import { useSettingsStore } from '../../stores/useSettingsStore';
import { GENERIC_UP_POSE } from '../../lib/robotPoses';
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

interface RobotModelProps {
  /** Override the joint angles to render. Omit to follow the live
   *  /joint_states stream from useRobotStore (the Printer > Live viewer's
   *  original behaviour). The Robot page passes an explicit array so it
   *  can drive the model from a local simulated pose instead. */
  joints?: number[];
  /** Render semi-transparent, for overlaying a second pose (see the
   *  deviation comparison in RobotJogViewer). Each RobotModel parses its own
   *  URDF, so the materials are per-instance and tinting one does not affect
   *  the other. */
  ghost?: boolean;
}

export default function RobotModel({ joints, ghost = false }: RobotModelProps = {}) {
  const [robot, setRobot] = useState<URDFRobot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const groupRef = useRef<THREE.Group>(null);
  const liveJointPositions = useRobotStore((s) => s.jointStates.positions);
  // robotConnected is the debounced "is there a real robot on the other
  // end" flag (see useRobotStatusPoll). Without it, the live store's
  // jointStates defaults to [0,0,0,0,0,0] whenever disconnected/no data has
  // ever arrived — which for a UR arm is a fully horizontal "lying down"
  // pose, not a neutral one. Fall back to GENERIC_UP_POSE instead so the
  // Printer > Live viewer never renders that degenerate pose as if it were
  // real data, and so it visually matches the Robot page's own disconnected
  // fallback (see RobotPage.tsx's simJoints).
  const robotConnected = useRobotStore((s) => s.robotConnected);
  const jointPositions = joints ?? (robotConnected ? liveJointPositions : GENERIC_UP_POSE);
  const robotModel = useSettingsStore((s) => s.robotModel);

  useEffect(() => {
    setRobot(null);
    setError(null);

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

        // Custom mesh loader
        loader.loadMeshCb = (url, manager, onLoad) => {
          // Normalize URL: remove double slashes, ensure starts with /
          const cleanUrl = url.replace(/\/+/g, '/');

          if (cleanUrl.endsWith('.dae')) {
            const colladaLoader = new ColladaLoader(manager);
            colladaLoader.load(cleanUrl, (result) => {
              onLoad(result.scene);
            }, undefined, () => {
              console.warn('DAE load failed, using placeholder:', cleanUrl);
              onLoad(new THREE.Object3D());
            });
          } else if (cleanUrl.endsWith('.stl')) {
            const stlLoader = new STLLoader(manager);
            stlLoader.load(cleanUrl, (geo) => {
              const mat = new THREE.MeshStandardMaterial({
                color: 0x888888,
                metalness: 0.4,
                roughness: 0.6,
              });
              const mesh = new THREE.Mesh(geo, mat);
              onLoad(mesh);
            }, undefined, () => {
              console.warn('STL load failed, using placeholder:', cleanUrl);
              onLoad(new THREE.Object3D());
            });
          } else {
            loader.defaultMeshLoader(cleanUrl, manager, onLoad);
          }
        };

        const parsed = loader.parse(urdfText);

        // Improve materials
        parsed.traverse((child) => {
          if (child instanceof THREE.Mesh) {
            child.castShadow = !ghost;
            child.receiveShadow = !ghost;
            if (ghost) {
              const mats = Array.isArray(child.material) ? child.material : [child.material];
              child.material = mats.map((m) => {
                const c = (m as THREE.Material).clone() as THREE.MeshStandardMaterial;
                c.transparent = true;
                c.opacity = 0.28;
                c.depthWrite = false;   // avoid the ghost occluding the real arm
                c.color?.set('#38bdf8');
                return c;
              });
              if (!Array.isArray(child.material)) child.material = child.material[0];
            }
          }
        });

        // Set initial home pose
        parsed.setJointValues({
          shoulder_pan_joint: 0,
          shoulder_lift_joint: -Math.PI / 2,
          elbow_joint: Math.PI / 2,
          wrist_1_joint: -Math.PI / 2,
          wrist_2_joint: -Math.PI / 2,
          wrist_3_joint: 0,
        });

        console.log(`URDF loaded (${robotModel}):`, Object.keys(parsed.joints).length, 'joints,', Object.keys(parsed.links).length, 'links');
        setRobot(parsed);
      })
      .catch((err) => {
        console.error('URDF load error:', err);
        setError(String(err));
      });
  }, [robotModel, ghost]);

  // Update joint values from ROS2 at render rate
  useFrame(() => {
    if (!robot || !jointPositions || jointPositions.length < 6) return;

    for (let i = 0; i < JOINT_NAMES.length; i++) {
      robot.setJointValue(JOINT_NAMES[i], jointPositions[i]);
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
    <group ref={groupRef} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]}>
      <primitive object={robot} />
    </group>
  );
}
