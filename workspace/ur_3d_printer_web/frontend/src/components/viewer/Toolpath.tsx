import { useMemo } from 'react';
import * as THREE from 'three';
import { usePrintStore } from '../../stores/usePrintStore';
import { MATERIALS, type MaterialType } from '../../lib/constants';

/** Per-layer tint: slight hue shift from bottom to top for depth. */
function layerTint(baseColor: THREE.Color, index: number, total: number): THREE.Color {
  const t = total > 1 ? index / (total - 1) : 0;
  const hsl = { h: 0, s: 0, l: 0 };
  baseColor.getHSL(hsl);
  // Slightly darken bottom layers, lighten top layers
  const lightness = hsl.l * (0.85 + t * 0.3);
  return new THREE.Color().setHSL(hsl.h, hsl.s, Math.min(lightness, 1.0));
}

/** Build a tube mesh along a path with material properties. */
function buildTubeMesh(
  points: THREE.Vector3[],
  radius: number,
  color: THREE.Color,
  roughness: number,
  metalness: number,
  opacity: number,
): THREE.Mesh | null {
  if (points.length < 2) return null;

  const curve = new THREE.CatmullRomCurve3(points, false, 'catmullrom', 0.1);
  const segments = Math.max(2, Math.min(points.length * 2, 200));
  const geometry = new THREE.TubeGeometry(curve, segments, radius, 6, false);
  const material = new THREE.MeshPhysicalMaterial({
    color,
    roughness,
    metalness,
    transparent: opacity < 1,
    opacity,
    clearcoat: roughness < 0.3 ? 0.3 : 0,
    clearcoatRoughness: 0.2,
    side: THREE.DoubleSide,
  });

  const mesh = new THREE.Mesh(geometry, material);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

/** Shared unit cylinder (Y-aligned, height=1, radius=1). Re-used across
 *  every InstancedMesh so the vertex buffer is tiny and only the per-
 *  instance Matrix4 grows with segment count. */
const UNIT_CYLINDER = new THREE.CylinderGeometry(1, 1, 1, 6, 1, true);
UNIT_CYLINDER.translate(0, 0.5, 0); // base at origin, top at y=1 → easier scale-as-length

/** Pre-allocated scratch objects to avoid GC churn in the hot loop. */
const _vMid = new THREE.Vector3();
const _vDir = new THREE.Vector3();
const _vScale = new THREE.Vector3();
const _qRot = new THREE.Quaternion();
const _mat = new THREE.Matrix4();
const _yUp = new THREE.Vector3(0, 1, 0);

/**
 * Build an InstancedMesh where each segment is rendered as a small
 * cylinder of the given radius. Looks like extruded filament strands but
 * costs one draw call per call regardless of segment count.
 */
function buildSegmentedInstancedMesh(
  segments: Array<[THREE.Vector3, THREE.Vector3]>,
  radius: number,
  color: THREE.Color,
  roughness: number,
  metalness: number,
  opacity: number,
): THREE.InstancedMesh | null {
  if (segments.length === 0) return null;

  const material = new THREE.MeshStandardMaterial({
    color,
    roughness,
    metalness,
    transparent: opacity < 1,
    opacity,
    side: THREE.DoubleSide,
  });

  const mesh = new THREE.InstancedMesh(UNIT_CYLINDER, material, segments.length);
  mesh.castShadow = true;
  mesh.receiveShadow = true;

  let written = 0;
  for (let i = 0; i < segments.length; i++) {
    const [a, b] = segments[i];
    _vDir.subVectors(b, a);
    const length = _vDir.length();
    if (length < 1e-6) continue;

    _vDir.divideScalar(length);
    _qRot.setFromUnitVectors(_yUp, _vDir);
    _vScale.set(radius, length, radius);
    _vMid.copy(a); // translate to start, cylinder grows from base upward by `length`
    _mat.compose(_vMid, _qRot, _vScale);
    mesh.setMatrixAt(written++, _mat);
  }

  if (written < segments.length) {
    // Trim away unused slots (degenerate zero-length segments).
    mesh.count = written;
  }
  mesh.instanceMatrix.needsUpdate = true;
  return mesh;
}

/**
 * Append the successive (a, b) segment pairs from a polyline to the
 * accumulator. We store endpoint pairs (not flat floats) so the instanced
 * builder can compute transforms in one pass.
 */
function appendSegments(
  accum: Array<[THREE.Vector3, THREE.Vector3]>,
  contour: THREE.Vector3[],
): void {
  for (let i = 1; i < contour.length; i++) {
    accum.push([contour[i - 1], contour[i]]);
  }
}

export default function Toolpath() {
  const sliceResult = usePrintStore((s) => s.sliceResult);
  const visibleMax = usePrintStore((s) => s.visibleLayerMax);

  const meshGroup = useMemo(() => {
    if (!sliceResult) return null;

    const { layers, nozzleDiameter, material: matKey } = sliceResult;
    const baseRadius = (nozzleDiameter || 0.4) / 2;
    const infillRadius = baseRadius * 0.85; // close to perimeter but visually a touch thinner
    const matDef = MATERIALS[(matKey || 'pla') as MaterialType]?.visual ?? MATERIALS.pla.visual;
    const baseColor = new THREE.Color(matDef.color);
    const group = new THREE.Group();

    const MAX_PERIMETER_TUBES_PER_LAYER = 32;

    for (let i = 0; i < layers.length; i++) {
      if (i >= visibleMax) break;

      const layer = layers[i];
      const layerColor = layerTint(baseColor, i, layers.length);

      // Slightly desaturate + lighten infill so the perimeter stays visually
      // dominant when both share the layer.
      const hsl = { h: 0, s: 0, l: 0 };
      layerColor.getHSL(hsl);
      const infillColor = new THREE.Color()
        .setHSL(hsl.h, hsl.s * 0.75, Math.min(hsl.l * 1.1, 0.92));

      const perimeterContours: THREE.Vector3[][] = [];
      const infillSegments: Array<[THREE.Vector3, THREE.Vector3]> = [];

      let currentContour: THREE.Vector3[] = [];
      let currentKind: 'perimeter' | 'infill' = 'perimeter';

      const flush = () => {
        if (currentContour.length < 2) return;
        if (currentKind === 'perimeter') {
          perimeterContours.push(currentContour);
        } else {
          appendSegments(infillSegments, currentContour);
        }
      };

      for (const pt of layer.points) {
        const v = new THREE.Vector3(pt.x, pt.z, pt.y);
        const ptKind = pt.kind ?? 'perimeter';

        if (ptKind !== currentKind && currentContour.length > 0) {
          flush();
          currentContour = [];
          currentKind = ptKind;
        }

        if (pt.type === 'extrude') {
          currentContour.push(v);
        } else {
          // Travel: terminate the current run, restart from this position.
          flush();
          currentContour = [v];
          currentKind = ptKind;
        }
      }
      flush();

      // Perimeter — smooth tube meshes for the outer wall.
      perimeterContours.sort((a, b) => b.length - a.length);
      const perimetersToRender = perimeterContours.slice(0, MAX_PERIMETER_TUBES_PER_LAYER);
      for (const contour of perimetersToRender) {
        const mesh = buildTubeMesh(
          contour, baseRadius, layerColor,
          matDef.roughness, matDef.metalness, matDef.opacity,
        );
        if (mesh) group.add(mesh);
      }

      // Infill — one InstancedMesh per layer; each segment is a cylinder.
      if (infillSegments.length > 0) {
        const infillMesh = buildSegmentedInstancedMesh(
          infillSegments,
          infillRadius,
          infillColor,
          // Slightly more matte than perimeter so the wall pops visually.
          Math.min(matDef.roughness + 0.15, 1.0),
          matDef.metalness * 0.7,
          Math.min(matDef.opacity, 0.92),
        );
        if (infillMesh) group.add(infillMesh);
      }
    }

    return group;
  }, [sliceResult, visibleMax]);

  if (!meshGroup) return null;

  return <primitive object={meshGroup} />;
}
