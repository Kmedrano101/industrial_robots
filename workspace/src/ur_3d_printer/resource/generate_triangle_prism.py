#!/usr/bin/env python3
"""
Generate an STL file for an equilateral triangular prism.
  - Base: equilateral triangle, 60mm sides, centered at origin
  - Height: 50mm (5cm)

Then generate G-code by slicing with 1mm layer height (vase/perimeter-only mode).
"""
import struct
import math
import os

# ─── Parameters ──────────────────────────────────────────────────────────────
SIDE = 60.0       # mm, triangle side length
HEIGHT = 50.0     # mm, prism height
LAYER_H = 1.0     # mm, layer height
NOZZLE_D = 0.4    # mm
FEED_PRINT = 1000 # mm/min
FEED_TRAVEL = 3000

# ─── Triangle vertices (equilateral, centered at origin) ────────────────────
R = SIDE / math.sqrt(3)  # circumradius
V = [
    (SIDE / 2, -R / 2),   # bottom-right
    (-SIDE / 2, -R / 2),  # bottom-left
    (0.0, R),              # top
]

# ─── Write binary STL ───────────────────────────────────────────────────────
def write_triangle(f, v1, v2, v3):
    """Write a single triangle facet to a binary STL."""
    # Compute normal via cross product
    e1 = (v2[0]-v1[0], v2[1]-v1[1], v2[2]-v1[2])
    e2 = (v3[0]-v1[0], v3[1]-v1[1], v3[2]-v1[2])
    nx = e1[1]*e2[2] - e1[2]*e2[1]
    ny = e1[2]*e2[0] - e1[0]*e2[2]
    nz = e1[0]*e2[1] - e1[1]*e2[0]
    mag = math.sqrt(nx*nx + ny*ny + nz*nz)
    if mag > 0:
        nx, ny, nz = nx/mag, ny/mag, nz/mag
    f.write(struct.pack('<3f', nx, ny, nz))
    for v in (v1, v2, v3):
        f.write(struct.pack('<3f', *v))
    f.write(struct.pack('<H', 0))  # attribute byte count


def generate_stl(filepath):
    """Generate binary STL for the triangular prism."""
    triangles = []

    # Bottom face (z=0) - 1 triangle
    b = [(V[i][0], V[i][1], 0.0) for i in range(3)]
    triangles.append((b[0], b[2], b[1]))  # normal pointing down

    # Top face (z=HEIGHT) - 1 triangle
    t = [(V[i][0], V[i][1], HEIGHT) for i in range(3)]
    triangles.append((t[0], t[1], t[2]))  # normal pointing up

    # 3 side faces - each is a rectangle = 2 triangles
    for i in range(3):
        j = (i + 1) % 3
        bl = (V[i][0], V[i][1], 0.0)
        br = (V[j][0], V[j][1], 0.0)
        tl = (V[i][0], V[i][1], HEIGHT)
        tr = (V[j][0], V[j][1], HEIGHT)
        triangles.append((bl, br, tr))
        triangles.append((bl, tr, tl))

    with open(filepath, 'wb') as f:
        f.write(b'\x00' * 80)  # header
        f.write(struct.pack('<I', len(triangles)))
        for tri in triangles:
            write_triangle(f, *tri)

    print(f"STL written: {filepath} ({len(triangles)} triangles)")


# ─── Generate G-code (perimeter-only slicing) ───────────────────────────────
def generate_gcode(filepath, stl_path):
    """Slice the prism into perimeter-only layers."""
    num_layers = int(HEIGHT / LAYER_H)
    e_total = 0.0

    # Compute extrusion per mm of travel (simplified volumetric)
    # E = (layer_height * nozzle_width * distance) / (pi/4 * filament_dia^2)
    # Simplified: just increment E proportionally to distance
    filament_dia = 1.75
    area_ratio = (LAYER_H * NOZZLE_D) / (math.pi / 4 * filament_dia ** 2)

    lines = [
        "; Triangular Prism - equilateral triangle",
        f"; Side: {SIDE}mm, Height: {HEIGHT}mm, Layers: {num_layers}",
        f"; Vertices: V1=({V[0][0]:.2f},{V[0][1]:.2f}), "
        f"V2=({V[1][0]:.2f},{V[1][1]:.2f}), V3=({V[2][0]:.2f},{V[2][1]:.2f})",
        f"; Generated from: {os.path.basename(stl_path)}",
        "G90 ; Absolute positioning",
        "G21 ; Millimeters",
        "G28 ; Home",
        "",
    ]

    for layer in range(num_layers):
        z = (layer + 0.5) * LAYER_H  # mid-layer Z
        lines.append(f"; Layer {layer} - z={z:.1f}mm")
        lines.append(f"G0 Z{z:.1f} F{FEED_TRAVEL}")

        if layer == 0:
            # Travel to first vertex on first layer
            lines.append(f"G0 X{V[0][0]:.2f} Y{V[0][1]:.2f} F{FEED_TRAVEL}")

        # Trace triangle: V0 → V1 → V2 → V0
        for i in range(3):
            j = (i + 1) % 3
            dx = V[j][0] - V[i][0]
            dy = V[j][1] - V[i][1]
            dist = math.sqrt(dx*dx + dy*dy)
            e_total += dist * area_ratio
            lines.append(
                f"G1 X{V[j][0]:.2f} Y{V[j][1]:.2f} F{FEED_PRINT} E{e_total:.2f}"
            )

        lines.append("")

    lines.append(f"G0 Z{HEIGHT + 5:.0f} F{FEED_TRAVEL} ; Lift")
    lines.append("G28 ; Home")

    with open(filepath, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    print(f"G-code written: {filepath} ({num_layers} layers, "
          f"perimeter = {SIDE * 3:.0f}mm/layer)")


# ─── Main ────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    base = os.path.dirname(os.path.abspath(__file__))
    stl_path = os.path.join(base, 'triangle_prism.stl')
    gcode_path = os.path.join(base, 'triangle_prism.gcode')

    generate_stl(stl_path)
    generate_gcode(gcode_path, stl_path)
