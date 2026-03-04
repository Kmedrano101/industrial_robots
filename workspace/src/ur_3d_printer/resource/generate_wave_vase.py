#!/usr/bin/env python3
# Copyright 2024 Kevin Medrano
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Generate a wave-vase STL model for multi-axis 3D printing.

Creates a vase with sinusoidal wall undulations that benefit from
multi-axis printing: the robot tilts the nozzle to follow the curved
surface for better layer adhesion and surface finish.

Usage:
    python3 generate_wave_vase.py -o wave_vase.stl
    python3 generate_wave_vase.py --wave-amplitude 12 --wave-freq-theta 7
"""

import argparse
import struct
import sys

import numpy as np


def generate_wave_vase(
    height: float = 80.0,          # mm
    base_radius: float = 30.0,     # mm
    top_radius: float = 40.0,      # mm
    wave_amplitude: float = 8.0,   # mm radial undulation
    wave_freq_z: int = 3,          # waves along height
    wave_freq_theta: int = 5,      # waves around circumference
    n_z: int = 100,                # vertical resolution
    n_theta: int = 80,             # angular resolution
):
    """Generate wave-vase mesh.

    Returns (tri_vertices, normals) where tri_vertices is (N,3,3) in mm
    and normals is (N,3).
    """
    z_vals = np.linspace(0.0, height, n_z)
    theta_vals = np.linspace(0.0, 2.0 * np.pi, n_theta, endpoint=False)

    # Surface points on the vase wall.
    points = np.zeros((n_z, n_theta, 3))

    for i, z in enumerate(z_vals):
        t = z / height
        r_base = base_radius + (top_radius - base_radius) * t

        for j, theta in enumerate(theta_vals):
            wave = wave_amplitude * np.sin(
                wave_freq_z * 2.0 * np.pi * z / height,
            ) * np.cos(wave_freq_theta * theta)
            r = r_base + wave

            points[i, j] = [r * np.cos(theta), r * np.sin(theta), z]

    # Triangulate quads on the surface.
    tri_verts = []
    normals = []

    for i in range(n_z - 1):
        for j in range(n_theta):
            jn = (j + 1) % n_theta

            v0 = points[i, j]
            v1 = points[i, jn]
            v2 = points[i + 1, jn]
            v3 = points[i + 1, j]

            # Triangle 1
            e1, e2 = v1 - v0, v2 - v0
            n1 = np.cross(e1, e2)
            nl = np.linalg.norm(n1)
            if nl > 1e-10:
                n1 /= nl
            tri_verts.append([v0, v1, v2])
            normals.append(n1)

            # Triangle 2
            e1, e2 = v2 - v0, v3 - v0
            n2 = np.cross(e1, e2)
            nl = np.linalg.norm(n2)
            if nl > 1e-10:
                n2 /= nl
            tri_verts.append([v0, v2, v3])
            normals.append(n2)

    # Bottom cap.
    center = np.array([0.0, 0.0, 0.0])
    for j in range(n_theta):
        jn = (j + 1) % n_theta
        tri_verts.append([center, points[0, jn], points[0, j]])
        normals.append(np.array([0.0, 0.0, -1.0]))

    return np.array(tri_verts), np.array(normals)


def write_binary_stl(filepath, tri_vertices, normals):
    """Write mesh to binary STL.

    Args:
        filepath: Output path.
        tri_vertices: (N, 3, 3) triangle vertices in mm.
        normals: (N, 3) face normals.
    """
    n_tris = len(normals)
    with open(filepath, 'wb') as f:
        header = b'Binary STL - Wave Vase for Multi-Axis Printing'
        header += b'\0' * (80 - len(header))
        f.write(header)
        f.write(struct.pack('<I', n_tris))

        for i in range(n_tris):
            f.write(struct.pack('<3f', *normals[i].astype(np.float32)))
            for v in range(3):
                f.write(struct.pack('<3f', *tri_vertices[i, v].astype(np.float32)))
            f.write(struct.pack('<H', 0))

    print(f'Wrote {n_tris} triangles to {filepath}', file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description='Generate wave-vase STL for multi-axis printing demo',
    )
    parser.add_argument(
        '-o', '--output', default='wave_vase.stl',
        help='Output STL file path',
    )
    parser.add_argument('--height', type=float, default=80.0)
    parser.add_argument('--base-radius', type=float, default=30.0)
    parser.add_argument('--top-radius', type=float, default=40.0)
    parser.add_argument('--wave-amplitude', type=float, default=8.0)
    parser.add_argument('--wave-freq-z', type=int, default=3)
    parser.add_argument('--wave-freq-theta', type=int, default=5)
    args = parser.parse_args()

    tri_verts, normals = generate_wave_vase(
        height=args.height,
        base_radius=args.base_radius,
        top_radius=args.top_radius,
        wave_amplitude=args.wave_amplitude,
        wave_freq_z=args.wave_freq_z,
        wave_freq_theta=args.wave_freq_theta,
    )

    write_binary_stl(args.output, tri_verts, normals)

    print(f'\nWave vase generated:', file=sys.stderr)
    print(f'  Height:     {args.height} mm', file=sys.stderr)
    print(f'  Base radius: {args.base_radius} mm', file=sys.stderr)
    print(f'  Top radius:  {args.top_radius} mm', file=sys.stderr)
    print(f'  Wave amp:    {args.wave_amplitude} mm', file=sys.stderr)
    print(f'  Triangles:   {len(normals)}', file=sys.stderr)


if __name__ == '__main__':
    main()
