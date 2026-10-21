import { describe, expect, it } from 'vitest';
import { EXTRUDER_MESHES, resolveExtruderUrdf } from './RobotModel';

const urdf = '<mesh filename="/meshes/extruders/__EXTRUDER_MESH__.stl" /> <origin xyz="0 0 __TOOL_LENGTH__" />';

describe('resolveExtruderUrdf', () => {
  it('substitutes the mesh and tool length of the reported profile', () => {
    const out = resolveExtruderUrdf(urdf, 'mahor_v5_m12_pro');
    expect(out).toContain('/meshes/extruders/mahor_v5_pro.stl');
    expect(out).toContain('xyz="0 0 0.1790"');
    expect(out).not.toContain('__');
  });

  it('falls back to the mounted extruder for unknown or missing profiles', () => {
    for (const model of [undefined, 'something_else']) {
      const out = resolveExtruderUrdf(urdf, model);
      expect(out).toContain(`/meshes/extruders/${EXTRUDER_MESHES.mahor_v5_m12_pro.file}.stl`);
    }
  });
});
