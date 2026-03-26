import { useMemo } from 'react';
import * as THREE from 'three';
import { usePrintStore } from '../../stores/usePrintStore';

/** Color gradient from blue (bottom) to red (top) for extrusion layers. */
function layerColor(index: number, total: number): THREE.Color {
  const t = total > 1 ? index / (total - 1) : 0;
  return new THREE.Color().setHSL(0.66 - t * 0.66, 0.9, 0.5); // blue → red
}

function LayerLines({ points, color, opacity = 1 }: { points: THREE.Vector3[]; color: THREE.Color; opacity?: number }) {
  const geometry = useMemo(() => {
    return new THREE.BufferGeometry().setFromPoints(points);
  }, [points]);

  const material = useMemo(() => {
    return new THREE.LineBasicMaterial({ color, transparent: opacity < 1, opacity });
  }, [color, opacity]);

  if (points.length < 2) return null;

  return <primitive object={new THREE.Line(geometry, material)} />;
}

export default function Toolpath() {
  const sliceResult = usePrintStore((s) => s.sliceResult);
  const visibleMax = usePrintStore((s) => s.visibleLayerMax);

  const lineElements = useMemo(() => {
    if (!sliceResult) return null;

    const { layers } = sliceResult;
    const elements: JSX.Element[] = [];

    for (let i = 0; i < layers.length; i++) {
      if (i >= visibleMax) break;

      const layer = layers[i];
      const extrudePoints: THREE.Vector3[] = [];
      const travelPoints: THREE.Vector3[] = [];

      for (const pt of layer.points) {
        const v = new THREE.Vector3(pt.x, pt.z, pt.y); // swap Y/Z for Three.js
        if (pt.type === 'extrude') {
          extrudePoints.push(v);
        } else {
          travelPoints.push(v);
        }
      }

      const color = layerColor(i, layers.length);

      if (extrudePoints.length > 1) {
        elements.push(
          <LayerLines key={`extrude-${i}`} points={extrudePoints} color={color} />,
        );
      }

      if (travelPoints.length > 1) {
        elements.push(
          <LayerLines key={`travel-${i}`} points={travelPoints} color={new THREE.Color('#6b7280')} opacity={0.3} />,
        );
      }
    }

    return elements;
  }, [sliceResult, visibleMax]);

  if (!lineElements) return null;

  return <group>{lineElements}</group>;
}
