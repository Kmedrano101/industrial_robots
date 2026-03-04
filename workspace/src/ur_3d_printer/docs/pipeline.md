# STL-to-Print Pipeline

## Overview

The ur_3d_printer package supports two paths from a 3D model to robot execution:

```
                        STL File (.stl)
                       /               \
              Planar Path          Multi-Axis Path
                  |                      |
           stl_slicer.py         multiaxis_slicer.py
           (resource/)            (resource/)
                  |                      |
           G-code (.gcode)        G-code + ORIENT
           (standard G0/G1)       (G0/G1 + ; ORIENT)
                  \                     /
                   \                   /
                    v                 v
                   GCodeParser.parse_file()
                         |
                      Toolpath
                   (Waypoint[], Layer[])
                         |
              TrajectoryPlanner.plan_toolpath_continuous()
                         |
                  JointTrajectory + ExtruderEvents
                         |
                  PrintNode._execute_print_loop()
                         |
              FollowJointTrajectory action
                         |
                    Robot Motion
```

## Step 1: Slicing (STL to G-code)

### Planar Slicing -- `resource/stl_slicer.py`

Standard horizontal slicing for layer-by-layer FDM printing.

```bash
python3 resource/stl_slicer.py model.stl \
    --layer-height 0.2 \
    --nozzle 0.4 \
    --scale 0.001 \
    --print-speed 1200 \
    -o model.gcode
```

**Process:**
1. `load_stl()` -- Reads binary or ASCII STL, extracts triangle vertices
2. `slice_at_z()` -- Intersects all triangles with a horizontal plane at each layer height, producing line segments
3. `connect_segments()` -- Stitches segments into closed polygons (contours)
4. `to_gcode()` -- Generates G0 (travel) and G1 (extrusion) commands with E values

**Output:** Standard G-code with `G0`, `G1`, `G28`, `G90`, `M82` commands. Units: millimeters, feed rates in mm/min.

### Multi-Axis Slicing -- `resource/multiaxis_slicer.py`

Non-planar slicing that tilts the nozzle to follow surface normals.

```bash
python3 resource/multiaxis_slicer.py model.stl \
    --layer-height 1.0 \
    --max-tilt 45 \
    --print-speed 50 \
    --travel-speed 150 \
    --robot ur5e \
    --no-collision-check \
    -o model.gcode
```

**Process:**
1. Uses `MultiAxisToolpathGenerator.generate_from_stl()` internally
2. Computes per-waypoint surface normals from nearby mesh triangles
3. Generates nozzle orientations that tilt toward the surface normal (clamped by `max_tilt`)
4. Smooths orientations across waypoints to avoid abrupt changes
5. Optionally validates IK and collisions, progressively reducing tilt on failing waypoints

**Output:** G-code with orientation comments:
```gcode
G1 X10.000 Y5.000 Z2.400 F1200.000 E0.035
; ORIENT nx=0.100 ny=0.000 nz=-0.995
G1 X10.500 Y5.200 Z2.450 F1200.000 E0.070
; ORIENT nx=0.150 ny=0.050 nz=-0.987
```

## Step 2: G-code Parsing

`GCodeParser` (`ur_3d_printer/gcode_parser.py`) converts G-code text into a `Toolpath` object.

```python
from ur_3d_printer import GCodeParser

parser = GCodeParser(
    filament_diameter=1.75,   # mm
    arc_resolution=1.0,       # mm per arc segment
    layer_z_threshold=0.1,    # mm Z change to trigger new layer
    default_feed_rate=1200.0  # mm/min
)
toolpath = parser.parse_file('/path/to/model.gcode')
```

**Supported commands:**

| Command | Description |
|---------|-------------|
| `G0` / `G00` | Rapid travel move (`is_travel=True`) |
| `G1` / `G01` | Linear extrusion move |
| `G2` / `G02` | Clockwise arc (discretized to line segments) |
| `G3` / `G03` | Counter-clockwise arc |
| `G28` | Home |
| `G90` | Absolute positioning mode |
| `G91` | Relative positioning mode |
| `G92` | Set position (coordinate reset) |
| `M82` | Absolute extrusion mode |
| `M83` | Relative extrusion mode |
| `M104`/`M109` | Set hotend temperature |
| `M140`/`M190` | Set bed temperature |
| `M106`/`M107` | Fan on/off |

**Unit conversions performed:**
- Positions: mm -> meters (divide by 1000)
- Feed rates: mm/min -> m/s (divide by 60000)
- Extrusion: E delta * filament cross-section area -> volumetric rate (m^3/s)

**Layer detection:** A new layer starts when Z increases by more than `layer_z_threshold` mm.

**ORIENT comments:** If a line contains `; ORIENT nx=... ny=... nz=...`, the parser sets the waypoint orientation from the surface normal vector, building a rotation matrix that tilts the nozzle toward that normal.

## Step 3: Toolpath Data Structure

The parser produces a `Toolpath` containing `Layer` objects, each containing `Waypoint` objects.

```
Toolpath
  +-- print_frame: np.ndarray (4x4)    # Identity by default
  +-- metadata: Dict                    # G-code stats
  +-- layers: List[Layer]
        +-- index: int
        +-- z_height: float             # meters
        +-- layer_height: float         # meters
        +-- waypoints: List[Waypoint]
              +-- position: np.ndarray  # (3,) XYZ in meters
              +-- orientation: np.ndarray  # (3,3) rotation matrix
              +-- feed_rate: float      # m/s
              +-- extrusion_rate: float # m^3/s (0 for travel)
              +-- is_travel: bool
              +-- layer_index: int
              +-- line_number: int      # Original G-code line
```

**Default orientation** (nozzle pointing straight down):
```
[[1, 0, 0],
 [0,-1, 0],
 [0, 0,-1]]
```

This corresponds to the UR tool0 Z-axis pointing downward (into the print bed).

## Step 4: Trajectory Planning

`TrajectoryPlanner.plan_toolpath_continuous()` converts the toolpath into a single `JointTrajectory`.

**Pipeline:**

```
Waypoints (print frame)
    |
    v
1. transform_to_robot_frame()    -- Apply print_frame (4x4) to all positions/orientations
    |
    v
2. densify_waypoints()           -- Insert intermediate points (max_segment_length = 2mm)
    |
    v
3. _apply_z_hop()                -- Insert lift/hover/lower at travel boundaries
    |
    v
4. compute_timestamps()          -- Trapezoidal velocity profile with corner blending
    |
    v
5. IK seed chaining              -- Solve IK for each waypoint, seeded from previous
    |                               Uses local URScrewKinematics solver
    |                               Joint normalization: wrap to within +/-pi of seed
    |                               Joint jump rejection: max delta > max_joint_jump
    v
6. check_trajectory()            -- Capsule-based self-collision check on all configs
    |
    v
7. _compute_continuous_velocities()  -- Central differences for joint velocities
    |                                   Zero at endpoints, enforce velocity limits
    v
JointTrajectory + List[(timestamp, bool)]  -- extruder event schedule
```

### Z-Hop Strategy

At travel/extrusion boundaries:
1. **Lift:** Current position -> current XY at `max(current_z, dest_z) + z_hop_height`
2. **Hover:** Travel laterally at elevated Z
3. **Lower:** Destination XY at elevated Z -> destination position

This avoids L-shaped paths and ensures the nozzle clears the tallest point.

### IK Seed Chaining

```
waypoint[0] -> IK(seed=current_joints) -> joints[0]
waypoint[1] -> IK(seed=joints[0])      -> joints[1]
waypoint[2] -> IK(seed=joints[1])      -> joints[2]
...
```

Each IK solution is **normalized** relative to its seed: joint angles are wrapped to minimize the difference from the seed, preventing unnecessary 2pi rotations. If any joint changes by more than `max_joint_jump` (default 0.5 rad), the solution is rejected as an IK branch switch (elbow flip or wrist flip).

## Step 5: Trajectory Execution

`PrintNode._execute_print_loop()` sends the trajectory to the robot:

1. **Home** -- Move to `home_joints` via FollowJointTrajectory
2. **Normalize** -- Adjust trajectory joint values relative to actual current joints (avoid 2pi wraps)
3. **Move to start** -- If robot isn't at trajectory start, move there first
4. **Start extruder scheduler** -- Background thread that enables/disables extruder at scheduled timestamps
5. **Execute** -- Send single continuous JointTrajectory to `/{controller}/follow_joint_trajectory`
6. **Finish** -- Retract extruder, lift nozzle, home robot
7. **State -> COMPLETED**

## Coordinate Frame Chain

```
STL file (mm)
    |  stl_slicer.py / multiaxis_slicer.py
    v
G-code (mm, mm/min)
    |  GCodeParser (mm -> m, mm/min -> m/s)
    v
Print frame (meters)           -- Waypoint positions relative to print_origin
    |  Toolpath.transform_to_robot_frame()
    |  Applies print_frame = T(print_origin_xyz) * R(print_origin_rpy)
    v
Robot base_link frame (meters) -- Cartesian poses for IK
    |  IK solver
    v
Joint space (radians)          -- JointTrajectory for execution
```

**Print origin defaults:** `[-0.3, 0.0, -0.01]` (30cm in front of robot, 1cm below base)

## Tool Offset Chain

The nozzle tip (TCP) is offset from the robot flange:

```
base_link
  +-- ... (arm links) ...
    +-- flange           -- Robot mounting face
      +-- tool0          -- UR tool frame (coincident with flange)
        +-- nozzle_tcp   -- Nozzle tip (tool_offset_xyz below tool0)
```

**Default tool offset:** `[0.0, 0.0, 0.105]` m (10.5 cm along tool Z-axis for FDM extruder)

The `TrajectoryPlanner` accounts for this by computing target flange poses: given a desired nozzle position and orientation, it applies the inverse tool offset to get the flange pose, then solves IK for that pose.

## Example: End-to-End Workflow

```bash
# 1. Slice an STL
python3 resource/stl_slicer.py resource/triangle_prism.stl \
    --layer-height 0.2 --scale 0.001 -o /tmp/prism.gcode

# 2. Launch the system (assumes UR driver already running)
ros2 launch ur_3d_printer print_ursim.launch.py \
    gcode_file:=/tmp/prism.gcode

# 3. Start the print
ros2 service call /print_node/start_print \
    ur_3d_printer/srv/StartPrint \
    "{gcode_filepath: '/tmp/prism.gcode'}"

# 4. Monitor progress
ros2 topic echo /print_node/progress
```

## See Also

- [Architecture](architecture.md) -- System design and state machines
- [Modules](modules.md) -- Detailed API for each module
- [Configuration](configuration.md) -- Tuning parameters
- [Operations](operations.md) -- Full operational guide
