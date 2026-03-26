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

export default function Toolpath() {
  const sliceResult = usePrintStore((s) => s.sliceResult);
  const visibleMax = usePrintStore((s) => s.visibleLayerMax);

  const meshGroup = useMemo(() => {
    if (!sliceResult) return null;

    const { layers, nozzleDiameter, material: matKey } = sliceResult;
    const radius = (nozzleDiameter || 0.4) / 2;
    const matDef = MATERIALS[(matKey || 'pla') as MaterialType]?.visual ?? MATERIALS.pla.visual;
    const baseColor = new THREE.Color(matDef.color);
    const group = new THREE.Group();

    for (let i = 0; i < layers.length; i++) {
      if (i >= visibleMax) break;

      const layer = layers[i];
      const color = layerTint(baseColor, i, layers.length);

      let currentContour: THREE.Vector3[] = [];

      for (const pt of layer.points) {
        const v = new THREE.Vector3(pt.x, pt.z, pt.y);

        if (pt.type === 'extrude') {
          currentContour.push(v);
        } else {
          if (currentContour.length >= 2) {
            const mesh = buildTubeMesh(
              currentContour, radius, color,
              matDef.roughness, matDef.metalness, matDef.opacity,
            );
            if (mesh) group.add(mesh);
          }
          currentContour = [v];
        }
      }

      if (currentContour.length >= 2) {
        const mesh = buildTubeMesh(
          currentContour, radius, color,
          matDef.roughness, matDef.metalness, matDef.opacity,
        );
        if (mesh) group.add(mesh);
      }
    }

    return group;
  }, [sliceResult, visibleMax]);

  if (!meshGroup) return null;

  return <primitive object={meshGroup} />;
}
