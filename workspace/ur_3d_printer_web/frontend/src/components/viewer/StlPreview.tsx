import { useEffect, useRef, useState, useCallback } from 'react';
import { useThree, type ThreeEvent } from '@react-three/fiber';
import { TransformControls } from '@react-three/drei';
import { usePrintStore } from '../../stores/usePrintStore';
import * as THREE from 'three';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';

/**
 * Find the largest flat face on a geometry (in world space, accounting for
 * the mesh's current rotation) and return a correction quaternion that,
 * when multiplied with the current quaternion, places that face flat on
 * the XZ plane (normal → -Y).
 */
function computeLayFlatCorrection(
  geometry: THREE.BufferGeometry,
  currentQuat: THREE.Quaternion,
): THREE.Quaternion {
  const pos = geometry.getAttribute('position');
  if (!pos) return new THREE.Quaternion();

  const triCount = geometry.index
    ? geometry.index.count / 3
    : pos.count / 3;

  // Normal rotation matrix from the mesh's current orientation
  const normalMatrix = new THREE.Matrix3().getNormalMatrix(
    new THREE.Matrix4().makeRotationFromQuaternion(currentQuat),
  );

  const clusters: Array<{ normal: THREE.Vector3; area: number }> = [];
  const ANGLE_THRESHOLD = 0.05; // ~3° tolerance

  const vA = new THREE.Vector3();
  const vB = new THREE.Vector3();
  const vC = new THREE.Vector3();
  const edge1 = new THREE.Vector3();
  const edge2 = new THREE.Vector3();
  const faceNormal = new THREE.Vector3();

  for (let i = 0; i < triCount; i++) {
    let ia: number, ib: number, ic: number;
    if (geometry.index) {
      ia = geometry.index.getX(i * 3);
      ib = geometry.index.getX(i * 3 + 1);
      ic = geometry.index.getX(i * 3 + 2);
    } else {
      ia = i * 3;
      ib = i * 3 + 1;
      ic = i * 3 + 2;
    }

    vA.fromBufferAttribute(pos, ia);
    vB.fromBufferAttribute(pos, ib);
    vC.fromBufferAttribute(pos, ic);

    edge1.subVectors(vB, vA);
    edge2.subVectors(vC, vA);
    faceNormal.crossVectors(edge1, edge2);

    const area = faceNormal.length() * 0.5;
    if (area < 1e-8) continue;

    faceNormal.normalize();

    // Transform normal to world space using mesh's current rotation
    faceNormal.applyMatrix3(normalMatrix).normalize();

    // Cluster by direction
    let found = false;
    for (const cluster of clusters) {
      if (1 - Math.abs(cluster.normal.dot(faceNormal)) < ANGLE_THRESHOLD) {
        cluster.area += area;
        found = true;
        break;
      }
    }

    if (!found) {
      clusters.push({ normal: faceNormal.clone(), area });
    }
  }

  // Find the cluster with largest total area — this is the best face to lay on
  let bestNormal = new THREE.Vector3(0, -1, 0);
  let bestArea = 0;
  for (const cluster of clusters) {
    if (cluster.area > bestArea) {
      bestArea = cluster.area;
      bestNormal = cluster.normal.clone();
    }
  }

  // Compute a correction rotation: rotate bestNormal (world space) → -Y
  const targetDown = new THREE.Vector3(0, -1, 0);
  const correction = new THREE.Quaternion().setFromUnitVectors(bestNormal, targetDown);

  // Final orientation = correction * current
  return correction.multiply(currentQuat);
}

const SELECTED_COLOR = new THREE.Color('#60a5fa');
const UNSELECTED_COLOR = new THREE.Color('#3b82f6');
const HOVER_COLOR = new THREE.Color('#93c5fd');
const OUTLINE_COLOR = new THREE.Color('#ffffff');

export default function StlPreview() {
  const uploadedFile = usePrintStore((s) => s.uploadedFile);
  const sliceResult = usePrintStore((s) => s.sliceResult);
  const objectSelected = usePrintStore((s) => s.objectSelected);
  const transformMode = usePrintStore((s) => s.transformMode);
  const setObjectSelected = usePrintStore((s) => s.setObjectSelected);
  const setObjectPosition = usePrintStore((s) => s.setObjectPosition);
  const setObjectRotation = usePrintStore((s) => s.setObjectRotation);
  const dropToBedCounter = usePrintStore((s) => s.dropToBedCounter);
  const layFlatCounter = usePrintStore((s) => s.layFlatCounter);
  const resetCounter = usePrintStore((s) => s.resetCounter);

  const [geometry, setGeometry] = useState<THREE.BufferGeometry | null>(null);
  const [hovered, setHovered] = useState(false);
  const meshRef = useRef<THREE.Mesh>(null!);
  const transformRef = useRef<any>(null);
  const { gl } = useThree();

  // Load STL geometry
  useEffect(() => {
    if (!uploadedFile || sliceResult) {
      setGeometry(null);
      setObjectSelected(false);
      return;
    }

    const loader = new STLLoader();
    const url = `/api/stl-preview?filepath=${encodeURIComponent(uploadedFile.filepath)}`;

    loader.load(
      url,
      (geo) => {
        geo.computeVertexNormals();
        geo.center();
        geo.computeBoundingBox();
        if (geo.boundingBox) {
          geo.translate(0, -geo.boundingBox.min.y, 0);
        }
        setGeometry(geo);
      },
      undefined,
      (err) => {
        console.warn('STL preview load failed:', err);
        if (uploadedFile.boundingBox) {
          const bb = uploadedFile.boundingBox;
          const w = bb.x_max - bb.x_min;
          const h = bb.y_max - bb.y_min;
          const d = bb.z_max - bb.z_min;
          const box = new THREE.BoxGeometry(w, d, h);
          box.translate(0, d / 2, 0);
          setGeometry(box);
        }
      },
    );

    return () => {
      setGeometry((prev) => {
        prev?.dispose();
        return null;
      });
    };
  }, [uploadedFile, sliceResult, setObjectSelected]);

  // Sync transform changes back to store when user drags the gizmo
  useEffect(() => {
    const controls = transformRef.current;
    if (!controls) return;

    const onDragging = (event: { value: boolean }) => {
      // Disable orbit controls while dragging the transform gizmo
      const orbitControls = (gl.domElement as any).__r3f_orbit;
      if (orbitControls) orbitControls.enabled = !event.value;
    };

    const onChange = () => {
      if (!meshRef.current) return;
      const pos = meshRef.current.position;
      const rot = meshRef.current.rotation;
      setObjectPosition([pos.x, pos.y, pos.z]);
      setObjectRotation([rot.x, rot.y, rot.z]);
    };

    controls.addEventListener('dragging-changed', onDragging);
    controls.addEventListener('objectChange', onChange);
    return () => {
      controls.removeEventListener('dragging-changed', onDragging);
      controls.removeEventListener('objectChange', onChange);
    };
  }, [gl, setObjectPosition, setObjectRotation, objectSelected]);

  // Drop to bed: compute world bounding box and adjust Y so bottom sits at Y=0
  useEffect(() => {
    if (dropToBedCounter === 0 || !meshRef.current) return;
    const mesh = meshRef.current;
    // Force update world matrix so bounding box accounts for rotation
    mesh.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(mesh);
    const yOffset = -box.min.y;
    mesh.position.y += yOffset;
    setObjectPosition([mesh.position.x, mesh.position.y, mesh.position.z]);
  }, [dropToBedCounter, setObjectPosition]);

  // Lay flat: find largest face considering current orientation, rotate it down, drop to bed
  useEffect(() => {
    if (layFlatCounter === 0 || !meshRef.current || !geometry) return;
    const mesh = meshRef.current;

    // Compute new quaternion that keeps current orientation context
    const newQuat = computeLayFlatCorrection(geometry, mesh.quaternion);
    mesh.quaternion.copy(newQuat);
    mesh.updateMatrixWorld(true);

    // Drop to bed after rotation
    const box = new THREE.Box3().setFromObject(mesh);
    mesh.position.y -= box.min.y;

    // Sync back to store
    const euler = new THREE.Euler().setFromQuaternion(newQuat);
    setObjectRotation([euler.x, euler.y, euler.z]);
    setObjectPosition([mesh.position.x, mesh.position.y, mesh.position.z]);
  }, [layFlatCounter, geometry, setObjectRotation, setObjectPosition]);

  // Reset: move mesh back to origin with no rotation, bottom on bed
  useEffect(() => {
    if (resetCounter === 0 || !meshRef.current || !geometry) return;
    const mesh = meshRef.current;

    mesh.position.set(0, 0, 0);
    mesh.quaternion.identity();
    mesh.rotation.set(0, 0, 0);
    mesh.updateMatrixWorld(true);

    // Recompute so bottom sits on Y=0 (same as initial load)
    geometry.computeBoundingBox();
    if (geometry.boundingBox) {
      mesh.position.y = -geometry.boundingBox.min.y;
    }

    setObjectPosition([mesh.position.x, mesh.position.y, mesh.position.z]);
    setObjectRotation([0, 0, 0]);
  }, [resetCounter, geometry, setObjectPosition, setObjectRotation]);

  // Cursor style
  useEffect(() => {
    gl.domElement.style.cursor = hovered ? 'pointer' : 'auto';
    return () => { gl.domElement.style.cursor = 'auto'; };
  }, [hovered, gl]);

  const handleClick = useCallback((e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation();
    setObjectSelected(!objectSelected);
  }, [objectSelected, setObjectSelected]);

  const handlePointerOver = useCallback((e: ThreeEvent<PointerEvent>) => {
    e.stopPropagation();
    setHovered(true);
  }, []);

  const handlePointerOut = useCallback(() => {
    setHovered(false);
  }, []);

  if (!geometry) return null;

  const color = objectSelected ? SELECTED_COLOR : hovered ? HOVER_COLOR : UNSELECTED_COLOR;
  const opacity = objectSelected ? 0.7 : hovered ? 0.65 : 0.5;

  const edgesGeo = new THREE.EdgesGeometry(geometry, 30);

  return (
    <>
      <mesh
        ref={meshRef}
        geometry={geometry}
        onClick={handleClick}
        onPointerOver={handlePointerOver}
        onPointerOut={handlePointerOut}
      >
        <meshStandardMaterial
          color={color}
          opacity={opacity}
          transparent
          side={THREE.DoubleSide}
        />
        {/* Simple solid white outline when selected */}
        {objectSelected && (
          <lineSegments geometry={edgesGeo}>
            <lineBasicMaterial color={OUTLINE_COLOR} />
          </lineSegments>
        )}
      </mesh>

      {/* TransformControls: arrows for translate, rings for rotate */}
      {objectSelected && meshRef.current && (
        <TransformControls
          ref={transformRef}
          object={meshRef.current}
          mode={transformMode}
          size={0.8}
          showX
          showY
          showZ
        />
      )}
    </>
  );
}
