# System Architecture

## Overview

The ur_3d_printer package converts a Universal Robots arm into a 3D printer. It is a ROS2 package built on `ament_cmake` with Python nodes, custom interfaces (messages, services, actions), URDF workcell descriptions, and launch files.

**Version:** 1.0.0

## Layered Architecture

```
+========================================================================+
|                        VISUALIZATION LAYER                             |
|  ToolpathVisualizer       DepositionVisualizer       RViz2             |
|  (layer coloring,         (3D tube geometry,         (saved views,     |
|   bounding box,            nozzle tracking,           TF tree,         |
|   print origin axes)       progress text)             joint states)    |
+========================================================================+
|                          CONTROL LAYER                                 |
|  PrintNode                  ExtruderControllerNode   MockController    |
|  (state machine,            (FDM/paste/digital IO,   (sim action       |
|   action server,             retraction/priming,       server,          |
|   trajectory execution,      rate ramping)             joint pub)       |
|   extruder scheduling)                                                 |
+========================================================================+
|                         PLANNING LAYER                                 |
|  TrajectoryPlanner        VelocityProfiler       WorkspaceValidator    |
|  (IK seed chaining,      (trapezoidal profile,  (bounds, reach,       |
|   joint normalization,     corner blending,       IK feasibility,      |
|   z-hop insertion,         densification)         singularity check)   |
|   collision filtering)                                                 |
|                       SelfCollisionChecker        MultiAxisPlanner     |
|                       (capsule geometry,          (surface normals,    |
|                        adjacency skipping,         tilt limiting,      |
|                        per-pair clearance)          STL slicing)       |
+========================================================================+
|                           DATA LAYER                                   |
|  GCodeParser              Toolpath / Layer / Waypoint                  |
|  (G0/G1/G2/G3,           (position, orientation, feed_rate,           |
|   arc discretization,      extrusion_rate, is_travel,                  |
|   mm->m conversion,        layer_index, line_number)                   |
|   layer detection)        stl_slicer / multiaxis_slicer (CLI tools)    |
+========================================================================+
```

## Module Dependency Graph

```
                    print_node
                   /    |     \
                  /     |      \
   trajectory_planner   |   extruder_controller
        /    |    \     |
       /     |     \    |
velocity_  collision_ workspace_    toolpath_visualizer
profiler   checker    validator     deposition_visualizer
       \     |     /
        \    |    /
         toolpath  <--  gcode_parser
                   <--  multiaxis_planner
```

Key dependencies:
- `print_node` orchestrates `trajectory_planner`, `extruder_controller`, and `workspace_validator`
- `trajectory_planner` uses `velocity_profiler`, `collision_checker`, and operates on `Toolpath` data
- `gcode_parser` and `multiaxis_planner` both produce `Toolpath` objects
- Visualization nodes are independent observers (subscribe to state/progress topics)

## ROS2 Node Graph

```
                                 /joint_states
                                      |
+------------------+    +-------------+-----------+
|  UR Driver /     |    |         print_node      |
|  MockController  |    |                         |
|                  |<---|  ~/state (PrintState)    |-----> toolpath_visualizer
|  /joint_states   |    |  ~/progress (Progress)  |-----> deposition_visualizer
|  FollowJoint     |    |  ~/tcp_trail (Markers)  |-----> rviz2
|  Trajectory      |    |  ~/planned_path (Mark.) |
+------------------+    |                         |
                        |  ~/start_print (srv)    |
                        |  ~/pause_print (srv)    |
                        |  ~/resume_print (srv)   |
                        |  ~/cancel_print (srv)   |
                        |  ~/calibrate_origin     |
                        |  ~/execute_print (act)  |
                        +--------+----------------+
                                 |
                    +------------+-------------+
                    |  extruder_controller     |
                    |  ~/set_extruder (srv)    |
                    |  ~/extruder_state (pub)  |
                    |  ~/extruder_command (pub)|
                    +--------------------------+
```

**Topics:**

| Topic | Type | Publisher | Subscriber(s) |
|-------|------|-----------|----------------|
| `/joint_states` | `sensor_msgs/JointState` | UR Driver / MockController | print_node |
| `~/state` | `PrintState` | print_node | toolpath_visualizer |
| `~/progress` | `PrintProgress` | print_node | toolpath_visualizer, deposition_visualizer |
| `~/tcp_trail` | `MarkerArray` | print_node | rviz2 |
| `~/planned_path` | `MarkerArray` | print_node | rviz2 |
| `~/extruder_state` | `ExtruderState` | extruder_controller | -- |
| `~/extruder_command` | `Float64` | extruder_controller | -- |
| `~/markers` | `MarkerArray` | toolpath_visualizer | rviz2 |
| `~/deposition` | `MarkerArray` | deposition_visualizer | rviz2 |

**Services:**

| Service | Type | Server |
|---------|------|--------|
| `~/start_print` | `StartPrint` | print_node |
| `~/pause_print` | `PausePrint` | print_node |
| `~/resume_print` | `ResumePrint` | print_node |
| `~/cancel_print` | `CancelPrint` | print_node |
| `~/calibrate_origin` | `CalibrateOrigin` | print_node |
| `~/set_extruder` | `SetExtruder` | extruder_controller |

**Actions:**

| Action | Type | Server | Client |
|--------|------|--------|--------|
| `~/execute_print` | `ExecutePrint` | print_node | CLI / user code |
| `/{controller}/follow_joint_trajectory` | `FollowJointTrajectory` | UR Driver / MockController | print_node |

## PrintNode State Machine

```
                         start_print /
                         execute_print
    +------+          +---------------+        +------------+
    | IDLE |--------->| LOADING_GCODE |------->| VALIDATING |
    +------+          +---------------+        +-----+------+
       ^                                             |
       |                                     validation pass
       |          cancel                             |
       |  +------------+        +--------+     +-----v----+
       +--| CANCELLING |<-------| HOMING |<----| HOMING   |
       |  +------------+  from  +---+----+     +----------+
       |       ^           any      |
       |       |           state    | at start position
       |       |                    v
       |       |              +-----------+     +-------------+
       |       +--------------| PRINTING  |<--->| TRAVEL_MOVE |
       |       |              +-----+-----+     +-------------+
       |       |                    |
       |       |              pause |          resume
       |       |                    v             |
       |       |              +--------+          |
       |       +--------------| PAUSED |----------+
       |                      +--------+
       |
       |    print complete      +------+         +-----------+
       +------------------------| HOMING |------->| COMPLETED |----> IDLE
                                +------+         +-----------+

    Any state -----> ERROR (on failure)
```

**States:**

| State | Value | Description |
|-------|-------|-------------|
| `IDLE` | 0 | Waiting for print job |
| `LOADING_GCODE` | 1 | Parsing G-code file into toolpath |
| `VALIDATING` | 2 | Running workspace validation (if enabled) |
| `HOMING` | 3 | Moving robot to home joint configuration |
| `CALIBRATING` | 4 | Setting print bed origin frame |
| `PRINTING` | 5 | Executing extrusion moves |
| `TRAVEL_MOVE` | 6 | Executing non-extrusion travel moves |
| `LAYER_CHANGE` | 7 | Transitioning between layers |
| `COMPLETED` | 8 | Print finished successfully |
| `PAUSED` | 9 | Print paused, awaiting resume or cancel |
| `CANCELLING` | 10 | Retracting and homing after cancel request |
| `ERROR` | 11 | Unrecoverable error occurred |

## Extruder State Machine

```
    +-----+    enable     +-----------+
    | OFF |-------------->| EXTRUDING |
    +-----+<--------------+-----------+
      ^ ^     disable          |
      | |                      | retract
      | |    auto-stop   +------------+
      | +----------------| RETRACTING |
      |                  +------------+
      |
      |      auto-stop   +---------+
      +------------------| PRIMING |
                         +---------+
```

| State | Value | Description |
|-------|-------|-------------|
| `OFF` | 0 | Extruder idle |
| `EXTRUDING` | 1 | Material flowing at commanded rate |
| `RETRACTING` | 2 | Pulling filament back to prevent oozing |
| `PRIMING` | 3 | Pushing filament forward to resume flow |

## Key Design Decisions

### Continuous Trajectory Execution
The system builds a **single continuous `JointTrajectory`** for the entire print rather than sending individual waypoint-to-waypoint commands. This avoids stop-start jitter between segments and lets the UR controller handle smooth interpolation. Extruder enable/disable events are scheduled by timestamp on a separate thread.

### Local IK Solver
Instead of calling the `/compute_ik` ROS service for each waypoint (which would add network latency for hundreds or thousands of points), `TrajectoryPlanner` uses a **local IK solver** (`URScrewKinematics` from `ur_kinematics_node`). This enables:
- IK seed chaining (each solution seeds the next)
- Joint normalization (wrap angles near seed to prevent 2pi jumps)
- Joint jump detection (reject solutions where any joint moves > `max_joint_jump` from seed)

### Capsule-Based Self-Collision Checking
Rather than loading full mesh collision geometry, each robot link is modeled as a **capsule** (cylinder with hemispherical caps). This enables O(n^2) pairwise distance checks with closed-form geometry, fast enough to validate entire trajectories. Adjacent link pairs (within `adjacency_skip=2` joints) are excluded since they can't collide by construction.

### Print Frame Abstraction
All G-code coordinates are parsed in the G-code coordinate frame (mm), converted to meters, and stored as waypoints in the **print frame**. The print frame is a 4x4 homogeneous transform (`print_origin_xyz` + `print_origin_rpy`) that maps print-space coordinates to `base_link`. This separation means the same G-code works regardless of where the print bed is positioned.

## TF Frame Tree

```
world
  +-- base_link (UR robot base)
  |     +-- shoulder_link
  |           +-- upper_arm_link
  |                 +-- forearm_link
  |                       +-- wrist_1_link
  |                             +-- wrist_2_link
  |                                   +-- wrist_3_link
  |                                         +-- flange
  |                                               +-- tool0
  |                                                     +-- extruder_mount
  |                                                           +-- (heatsink/heatbreak/nozzle)
  |                                                                 +-- nozzle_tcp
  +-- print_bed_link
        +-- print_origin
  +-- optical_table_surface (if included)
```

## See Also

- [Pipeline](pipeline.md) -- STL-to-print data flow
- [Modules](modules.md) -- Detailed module reference
- [Configuration](configuration.md) -- All parameters
- [Interfaces](interfaces.md) -- ROS2 message/service/action definitions
- [Operations](operations.md) -- Running and troubleshooting
