# Module Reference

All modules are in `ur_3d_printer/ur_3d_printer/`. Imports are lazy -- importing the package does not load all dependencies.

```python
from ur_3d_printer import GCodeParser, Toolpath, TrajectoryPlanner  # etc.
```

---

## toolpath.py -- Core Data Structures

Defines the three primary data structures used throughout the system.

### `Waypoint` (dataclass)

| Field | Type | Description |
|-------|------|-------------|
| `position` | `np.ndarray (3,)` | XYZ in meters (print frame) |
| `orientation` | `np.ndarray (3,3)` | Rotation matrix (default: nozzle-down) |
| `feed_rate` | `float` | Target speed in m/s |
| `extrusion_rate` | `float` | Volumetric rate in m^3/s (0 for travel) |
| `is_travel` | `bool` | True for non-extruding moves |
| `layer_index` | `int` | Layer this waypoint belongs to |
| `line_number` | `int` | Source G-code line number |

**Properties:** `x`, `y`, `z` (position components)

**Methods:**
- `distance_to(other) -> float` -- Euclidean distance to another waypoint
- `to_homogeneous() -> np.ndarray (4,4)` -- 4x4 homogeneous transform

**Default orientation** (nozzle pointing straight down):
```python
np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]])
```

### `Layer` (dataclass)

| Field | Type | Description |
|-------|------|-------------|
| `index` | `int` | Layer number (0-indexed) |
| `z_height` | `float` | Z position in meters |
| `waypoints` | `List[Waypoint]` | All waypoints in this layer |
| `layer_height` | `float` | Vertical distance from previous layer |
| `surface_normals` | `Optional[np.ndarray]` | For non-planar layers |

**Properties:**
- `num_waypoints`, `extrusion_waypoints`, `travel_waypoints`
- `path_length()`, `extrusion_length()`

### `Toolpath` (dataclass)

| Field | Type | Description |
|-------|------|-------------|
| `layers` | `List[Layer]` | All layers |
| `print_frame` | `np.ndarray (4,4)` | Print-to-robot transform (default: identity) |
| `metadata` | `Dict` | G-code statistics |

**Properties:**
- `num_layers`, `num_waypoints`, `all_waypoints`
- `bounding_box` -- `(min_xyz, max_xyz)` in print frame
- `estimated_time` -- Sum of segment distances / feed rates

**Methods:**
- `transform_to_robot_frame() -> List[Waypoint]` -- Applies `print_frame` to all waypoints
- `bounding_box_robot_frame()` -- Bounding box in robot coordinates

---

## gcode_parser.py -- G-code Parser

Parses standard G-code files into `Toolpath` objects.

### `GCodeParser`

**Constructor:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `filament_diameter` | `float` | 1.75 | mm |
| `arc_resolution` | `float` | 1.0 | mm per arc segment |
| `layer_z_threshold` | `float` | 0.1 | mm Z change to trigger new layer |
| `default_feed_rate` | `float` | 1200.0 | mm/min |

**Public API:**
- `parse_file(filepath: str) -> Toolpath`
- `parse_lines(lines: List[str]) -> Toolpath`

**Supported G-codes:** G0/G1 (linear), G2/G3 (arcs), G28 (home), G90/G91 (abs/rel positioning), G92 (set position), M82/M83 (abs/rel extrusion), M104/M109/M140/M190 (temperatures), M106/M107 (fan)

**Unit conversions:** mm -> m, mm/min -> m/s, E delta -> volumetric rate (m^3/s)

**ORIENT parsing:** Lines containing `; ORIENT nx=... ny=... nz=...` set waypoint orientation from the surface normal vector.

---

## velocity_profiler.py -- Velocity Profiling

Computes timestamps for waypoint sequences using trapezoidal velocity profiles with corner blending.

### `VelocityProfiler`

**Constructor:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_print_velocity` | `float` | 0.05 | m/s |
| `max_travel_velocity` | `float` | 0.15 | m/s |
| `max_acceleration` | `float` | 0.5 | m/s^2 |
| `corner_blend_radius` | `float` | 0.002 | m |
| `min_segment_time` | `float` | 0.01 | s |

**Public API:**
- `compute_timestamps(waypoints: List[Waypoint]) -> List[float]` -- Returns cumulative timestamps
- `densify_waypoints(waypoints: List[Waypoint], max_segment_length: float) -> List[Waypoint]` -- Insert intermediate waypoints

**Algorithm:**
1. Compute junction (corner) velocities from path deviation angle: `v = sqrt(a * r * sin(theta/2) / (1 - sin(theta/2)))`
2. Forward pass: limit velocity by acceleration from previous point
3. Backward pass: limit velocity by deceleration to next point
4. Final velocity = min(forward, backward, max_velocity)
5. Timestamps from segment distance / average velocity

---

## trajectory_planner.py -- Cartesian-to-Joint Planning

Converts `Toolpath` objects into `JointTrajectory` messages using local IK solving.

### `TrajectoryPlanner`

**Constructor:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `node` | `Node` | -- | ROS2 node (for logging) |
| `tool_offset` | `np.ndarray` | `eye(4)` | 4x4 flange-to-nozzle transform |
| `robot_model` | `str` | `"ur5e"` | Robot model for IK/collision |
| `ik_method` | `str` | `"lm"` | `"lm"`, `"newton"`, or `"analytical"` |
| `ik_max_iterations` | `int` | 100 | Max IK solver iterations |
| `ik_tolerance` | `float` | 1e-6 | IK convergence tolerance |
| `ik_timeout` | `float` | 5.0 | IK timeout in seconds |
| `max_segment_length` | `float` | 0.002 | m, for densification |
| `z_hop_enabled` | `bool` | True | Insert z-hops at travel boundaries |
| `z_hop_height` | `float` | 0.005 | m, z-hop clearance |
| `max_joint_jump` | `float` | 0.5 | rad, reject IK branch switches |
| `joint_velocity_limits` | `List[float]` | `[pi]*6` | rad/s per joint |
| `singularity_velocity_scale` | `float` | 0.3 | Slowdown near singularities |
| `enable_collision_check` | `bool` | True | Run self-collision check |
| `collision_safety_margin` | `float` | 0.02 | m, collision margin |
| `extruder_radius` | `float` | 0.025 | m, extruder capsule radius |

**Public API:**
- `configure_profiler(**kwargs)` -- Update VelocityProfiler parameters
- `plan_toolpath(toolpath, current_joints) -> List[Tuple[JointTrajectory, bool]]` -- Segmented planning (splits at travel/extrusion boundaries)
- `plan_toolpath_continuous(toolpath, current_joints) -> Tuple[JointTrajectory, List[Tuple[float, bool]]]` -- Single continuous trajectory with extruder event schedule
- `plan_single_waypoint(waypoint, seed, print_frame) -> Optional[np.ndarray]` -- Solve IK for one waypoint

**Internal pipeline:** See [Pipeline](pipeline.md#step-4-trajectory-planning) for the full planning sequence.

**Key behaviors:**
- **IK seed chaining:** Each waypoint's IK is seeded from the previous solution
- **Joint normalization:** Angles wrapped to within +/-pi of seed
- **Joint jump rejection:** Solutions with max delta > `max_joint_jump` are rejected
- **Z-hop:** Uses `max(current_z, dest_z) + z_hop_height` for clearance
- **Velocity computation:** Central differences with zero at endpoints; time-scaled to enforce joint velocity limits

---

## collision_checker.py -- Self-Collision Detection

Capsule-based self-collision checking for UR robots.

### `SelfCollisionChecker`

**Constructor:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `robot_model` | `str` | `"ur5e"` | Robot model (`ur3e`, `ur5e`, `ur10e`) |
| `extruder_length` | `float` | 0.105 | m, extruder capsule length |
| `extruder_radius` | `float` | 0.025 | m, extruder capsule radius |
| `safety_margin` | `float` | 0.02 | m, added to all clearance checks |
| `adjacency_skip` | `int` | 2 | Skip pairs within N joints |

**Public API:**
- `check_config(joint_angles: np.ndarray) -> CollisionResult` -- Check single configuration
- `check_trajectory(joint_trajectory: np.ndarray) -> List[Tuple[int, CollisionResult]]` -- Check all configs, return only collisions
- `min_clearance_trajectory(joint_trajectory) -> Tuple[float, int, Tuple[str, str]]` -- Minimum clearance across trajectory

**`CollisionResult`:**

| Field | Type | Description |
|-------|------|-------------|
| `has_collision` | `bool` | True if any pair is in collision |
| `min_clearance` | `float` | Smallest clearance (negative = penetration) |
| `collision_pairs` | `List[Tuple[str, str]]` | Link pairs in collision |
| `clearances` | `Dict[Tuple[str, str], float]` | Per-pair clearance values |

**Capsule model:** Each link modeled as a capsule (cylinder + hemispherical caps). The extruder extends from the flange along the flange Z-axis.

**Link names:** `base_shoulder`, `shoulder_elbow`, `elbow_wrist1`, `wrist1_wrist2`, `wrist2_wrist3`, `wrist3_flange`, `extruder`

**UR5e capsule radii:** `[0.075, 0.060, 0.050, 0.045, 0.045, 0.040]` m

---

## workspace_validator.py -- Pre-Flight Validation

Validates a toolpath before execution by checking reachability, bounds, IK feasibility, and singularity proximity.

### `WorkspaceValidator`

**Constructor:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `node` | `Node` | -- | ROS2 node |
| `tool_offset` | `np.ndarray` | -- | 4x4 transform |
| `workspace_bounds` | `Tuple` | -- | `(min_xyz, max_xyz)` |
| `singularity_threshold` | `float` | 0.05 | Min singular value |
| `sample_every_n` | `int` | 10 | Check every Nth waypoint |
| `min_reach_radius` | `float` | 0.0 | m, inner reach limit |
| `max_reach_radius` | `float` | inf | m, outer reach limit |

**Public API:**
- `validate(toolpath: Toolpath) -> ValidationResult`

**`ValidationResult`:**

| Field | Type | Description |
|-------|------|-------------|
| `is_valid` | `bool` | All checks passed |
| `unreachable_waypoints` | `List[int]` | Waypoints failing IK |
| `singular_waypoints` | `List[int]` | Waypoints near singularities |
| `out_of_bounds_waypoints` | `List[int]` | Waypoints outside workspace |
| `messages` | `List[str]` | Human-readable diagnostics |
| `total_checked` | `int` | Number of sampled waypoints |
| `total_reachable` | `int` | Number passing IK |
| `reachability_pct` | `float` | Percentage reachable |

**Checks performed:**
1. Rectangular bounding box vs `workspace_min`/`workspace_max`
2. Radial distance: inside `min_reach_radius` (too close) or outside `max_reach_radius` (too far)
3. IK feasibility via `ComputeIK` service (sampled)
4. Jacobian SVD: minimum singular value < `singularity_threshold`

---

## extruder_controller.py -- Extruder Control

ROS2 node that controls the extruder hardware (or simulated output).

### `ExtruderControllerNode`

**Node name:** `extruder_controller`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `extruder_type` | `str` | `"fdm"` | `"fdm"` or `"paste"` |
| `control_method` | `str` | `"topic"` | `"topic"`, `"digital_io"`, or `"analog"` |
| `nozzle_diameter` | `float` | 0.4 | mm |
| `filament_diameter` | `float` | 1.75 | mm |
| `max_rate` | `float` | 0.00001 | m^3/s |
| `retraction_distance` | `float` | 0.005 | m |
| `retraction_speed` | `float` | 0.001 | m/s |
| `prime_distance` | `float` | 0.005 | m |
| `prime_speed` | `float` | 0.0005 | m/s |
| `publish_rate` | `float` | 50.0 | Hz |
| `transition_time` | `float` | 0.3 | s, ramp duration |

**ROS2 interface:**
- Service `~/set_extruder` (`SetExtruder`) -- Enable/disable, set rate, retract, prime
- Publisher `~/extruder_state` (`ExtruderState`) -- State at `publish_rate`
- Publisher `~/extruder_command` (`Float64`) -- Raw command value

**Control methods:**
- `topic` -- Publishes raw Float64 value
- `digital_io` -- Publishes 1.0 (on) or 0.0 (off)
- `analog` -- Scales rate to 0-10V range

**States:** OFF (0), EXTRUDING (1), RETRACTING (2), PRIMING (3)

**Behavior:** Rate ramping over `transition_time`. Retraction/priming auto-completes and returns to OFF.

---

## print_node.py -- Main Print Controller

The central orchestrator. Manages the print state machine, trajectory execution, and extruder scheduling.

### `PrintNode`

**Node name:** `print_node`

See [Architecture](architecture.md#printnode-state-machine) for the full state machine diagram.

**Parameters:** See [Configuration](configuration.md#print-node-parameters) for the complete list.

**ROS2 interface:** See [Interfaces](interfaces.md) for all services, topics, and actions.

**Key methods:**
- `_handle_start_print(request, response)` -- Parse G-code, optionally validate, begin printing
- `_execute_print_loop()` -- Main execution: home -> move to start -> execute trajectory -> finish
- `_extruder_scheduler(events)` -- Background thread that enables/disables extruder at timestamps
- `_handle_pause(request, response)` -- Cancel current trajectory goal, retract extruder
- `_handle_resume(request, response)` -- Re-plan from current position and resume

**Trajectory execution:** Sends a single continuous `JointTrajectory` via `FollowJointTrajectory` action to the configured trajectory controller (default: `scaled_joint_trajectory_controller`).

---

## multiaxis_planner.py -- Multi-Axis Toolpath Generation

Generates non-planar toolpaths from STL files with variable nozzle orientations.

### `MultiAxisConfig` (dataclass)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `layer_height` | `float` | 0.001 | m (1 mm) |
| `nozzle_diameter` | `float` | 0.0004 | m (0.4 mm) |
| `max_tilt_angle` | `float` | 45.0 | degrees |
| `tilt_smoothing_window` | `int` | 5 | Waypoints for orientation smoothing |
| `enable_collision_check` | `bool` | True | Validate IK + collision |
| `collision_safety_margin` | `float` | 0.02 | m |
| `robot_model` | `str` | `"ur5e"` | For collision checking |
| `waypoint_spacing` | `float` | 0.002 | m |
| `print_speed` | `float` | 0.05 | m/s |
| `travel_speed` | `float` | 0.15 | m/s |

### `MultiAxisToolpathGenerator`

**Constructor:** `config: MultiAxisConfig`

**Public API:**
- `generate_from_stl(stl_filepath, print_frame) -> Toolpath` -- Full pipeline: load STL, slice, compute normals, generate oriented waypoints
- `validate_toolpath_collisions(toolpath, ik_solver, seed) -> Tuple[Toolpath, dict]` -- Check IK + collision for each waypoint; progressively reduce tilt toward vertical if collision detected

**Key functions:**
- `load_stl_mesh()` -- Binary + ASCII STL loading (mm -> m)
- `orientation_from_normal(normal, max_tilt)` -- Rotation matrix from surface normal, clamped tilt
- `smooth_orientations(waypoints, window)` -- Moving-average smoothing of nozzle Z-axis
- `interpolate_orientations(R1, R2, alpha)` -- SVD-based rotation blending
- `compute_surface_normal_at_point()` -- Inverse-distance-weighted normal from nearby triangles

---

## toolpath_visualizer.py -- RViz Toolpath Display

Publishes RViz markers showing the toolpath with layer-based coloring.

### `ToolpathVisualizer`

**Node name:** `toolpath_visualizer`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `publish_rate` | `float` | 2.0 | Hz |
| `frame_id` | `str` | `"world"` | TF frame |
| `line_width` | `float` | 0.001 | m |
| `show_travel` | `bool` | True | Show travel moves |
| `show_bounding_box` | `bool` | True | Show wireframe box |
| `gcode_file` | `str` | `""` | Auto-load on startup |
| `print_origin_xyz` | `List[float]` | `[-0.3, 0, -0.01]` | Print origin |
| `print_origin_rpy` | `List[float]` | `[0, 0, 0]` | Print orientation |
| `filament_diameter` | `float` | 1.75 | mm |

**Subscribes to:** `/print_node/state`, `/print_node/progress`

**Publishes:** `~/markers` (`MarkerArray`) -- LINE_STRIP markers per layer

**Layer coloring:** Completed = green, current = yellow, remaining = gray, pre-print = blue gradient

---

## deposition_visualizer.py -- 3D Material Visualization

Renders 3D tube geometry showing deposited material, active extrusion, and nozzle position.

### `DepositionVisualizer`

**Node name:** `deposition_visualizer`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `gcode_file` | `str` | `""` | G-code file to visualize |
| `frame_id` | `str` | `"world"` | TF frame |
| `print_origin_xyz` | `List[float]` | `[-0.3, 0, -0.01]` | Print origin |
| `tube_sides` | `int` | 8 | Polygon sides for tube cross-section |
| `tube_radius_scale` | `float` | 1.0 | Scale factor for tube radius |
| `color_scheme` | `str` | `"pla"` | `"pla"` or `"gradient"` |
| `demo_mode` | `bool` | True | Auto-animate vs live tracking |
| `speed_scale` | `float` | 5.0 | Animation speed multiplier |
| `publish_rate` | `float` | 30.0 | Hz |
| `nozzle_diameter` | `float` | 0.0004 | m |

**Publishes:** `~/deposition` (`MarkerArray`) -- TRIANGLE_LIST tube geometry, nozzle sphere, progress text

**Modes:**
- `demo` -- Auto-animates through the toolpath at `speed_scale`x speed
- `live` -- Tracks actual print progress from `/print_node/progress`

---

## mock_controller.py -- Simulation Controller

Simulates a UR trajectory controller for testing without a real robot or URSim.

### `MockTrajectoryController`

**Node name:** `mock_trajectory_controller`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `publish_rate` | `float` | 50.0 | Hz |
| `speed_scale` | `float` | 1.0 | Trajectory speed multiplier |
| `home_joints` | `List[float]` | `[0, -pi/2, pi/2, -pi/2, -pi/2, 0]` | Initial position |

**Publishes:** `/joint_states` (`JointState`) at `publish_rate`

**Action server:** `/joint_trajectory_controller/follow_joint_trajectory` (`FollowJointTrajectory`)

Steps through trajectory waypoints at correct timing (scaled by `speed_scale`), publishing joint states so RViz animates the robot. Supports goal cancellation.

---

## See Also

- [Architecture](architecture.md) -- System design overview
- [Pipeline](pipeline.md) -- Data flow from STL to execution
- [Configuration](configuration.md) -- All parameter details
- [Interfaces](interfaces.md) -- ROS2 interface definitions
