import { useEffect, useRef, useState } from 'react';
import { useFrame } from '@react-three/fiber';
import { useRobotStore } from '../../stores/useRobotStore';
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

export default function RobotModel() {
  const [robot, setRobot] = useState<URDFRobot | null>(null);
  const groupRef = useRef<THREE.Group>(null);
  const jointPositions = useRobotStore((s) => s.jointStates.positions);

  // Load URDF
  useEffect(() => {
    const loader = new URDFLoader();
    loader.parseCollision = false;
    loader.parseVisual = true;

    // Custom mesh loader: handles DAE (Collada) and STL files
    loader.loadMeshCb = (url, manager, onLoad) => {
      if (url.endsWith('.dae')) {
        const colladaLoader = new ColladaLoader(manager);
        colladaLoader.load(url, (result) => {
          onLoad(result.scene);
        }, undefined, (err) => {
          console.warn('DAE load failed:', url, err);
          onLoad(new THREE.Object3D());
        });
      } else if (url.endsWith('.stl')) {
        const stlLoader = new STLLoader(manager);
        stlLoader.load(url, (geo) => {
          const mat = new THREE.MeshStandardMaterial({ color: 0x888888, metalness: 0.4, roughness: 0.6 });
          const mesh = new THREE.Mesh(geo, mat);
          onLoad(mesh);
        }, undefined, (err) => {
          console.warn('STL load failed:', url, err);
          onLoad(new THREE.Object3D());
        });
      } else {
        // GLB/GLTF fallback
        loader.defaultMeshLoader(url, manager, onLoad);
      }
    };

    loader.load(
      '/robot.urdf',
      (loadedRobot) => {
        // Make robot meshes cast/receive shadows and improve materials
        loadedRobot.traverse((child) => {
          if (child instanceof THREE.Mesh) {
            child.castShadow = true;
            child.receiveShadow = true;
          }
        });

        setRobot(loadedRobot);
      },
      undefined,
      (err) => {
        console.error('URDF load failed:', err);
      },
    );
  }, []);

  // Update joint values from ROS2 joint states at render rate
  useFrame(() => {
    if (!robot || !jointPositions || jointPositions.length < 6) return;

    for (let i = 0; i < JOINT_NAMES.length; i++) {
      robot.setJointValue(JOINT_NAMES[i], jointPositions[i]);
    }
  });

  if (!robot) return null;

  return (
    <group ref={groupRef}>
      <primitive object={robot} />
    </group>
  );
}
