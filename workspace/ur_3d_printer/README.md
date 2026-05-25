# UR 3D Printer

A ROS2 package that turns any Universal Robots arm (UR3e–UR30) into a 3D printer.
G-code is parsed, converted to Cartesian waypoints, solved through screw-theory IK,
and streamed to the robot as `JointTrajectory` messages — all in real-time.

---

## Quick Start (Standalone — no robot needed)

```bash
# 1. Build
cd ~/src/industrial_robots/workspace
source /opt/ros/jazzy/setup.bash
colcon build --packages-select ur_3d_printer ur_kinematics_node ur_screw_kinematics \
             ur_kinematics_msgs --symlink-install
source install/setup.bash

# 2. Slice an STL to G-code (example included)
python3 src/ur_3d_printer/resource/stl_slicer.py \
    src/ur_3d_printer/resource/chair.stl \
    -o /tmp/chair.gcode --layer-height 1.0

# 3. Launch (opens RViz with robot model + toolpath)
ros2 launch ur_3d_printer print_standalone.launch.py \
    gcode_file:=/tmp/chair.gcode \
    speed_scale:=10.0

# 4. Start the print
ros2 service call /print_node/start_print ur_3d_printer/srv/StartPrint \
    "{gcode_filepath: '/tmp/chair.gcode'}"
```

RViz will show the robot moving along the toolpath.
`speed_scale:=10.0` plays back at 10× real time.

---

## Launch Modes

| Mode | Launch file | When to use |
|------|-------------|-------------|
| **Standalone** | `print_standalone.launch.py` | Development, no robot or URSim needed |
| **URSim app** | `print_ursim.launch.py` | Driver already running (e.g. in Docker) |
| **Full driver** | `print_driver.launch.py` | One-command bring-up against URSim or real robot |

### Standalone

```bash
ros2 launch ur_3d_printer print_standalone.launch.py \
    gcode_file:=/tmp/chair.gcode \
    speed_scale:=5.0        # playback multiplier (default 1.0 = real time)
```

Launches: kinematics server · mock trajectory controller · toolpath visualizer · print node · RViz

### URSim — app nodes only

```bash
# Assumes ur_control.launch.py is already running (e.g. in a Docker container)
ros2 launch ur_3d_printer print_ursim.launch.py \
    gcode_file:=/tmp/chair.gcode \
    robot_model:=ur5e
```

Launches: static TF · extruder + bed visualizers · kinematics server · extruder controller · toolpath visualizer · print node · RViz

### Full driver (URSim or real robot)

```bash
# URSim default IP
ros2 launch ur_3d_printer print_driver.launch.py \
    robot_ip:=172.17.0.2 \
    gcode_file:=/tmp/chair.gcode

# Real robot
ros2 launch ur_3d_printer print_driver.launch.py \
    robot_ip:=192.168.1.100 \
    ur_type:=ur10e \
    gcode_file:=/tmp/chair.gcode
```

Launches: `ur_control.launch.py` (full UR driver with workcell URDF) · kinematics server · extruder controller · toolpath visualizer · print node · RViz

---

## URSim Setup

```bash
# 1. Start URSim container
docker compose --profile sim up

# 2. Open teach pendant: http://localhost:6080/vnc.html
#    Power ON → ON → START

# 3. Installation → URCaps → External Control
#    Host IP: your machine's IP  (run: hostname -I | awk '{print $1}')
#    Port:    50002

# 4. Create program: [External Control] → PLAY

# 5. Launch the printer (full driver mode)
source /opt/ros/jazzy/setup.bash
source ~/src/industrial_robots/workspace/install/setup.bash
ros2 launch ur_3d_printer print_driver.launch.py \
    robot_ip:=172.17.0.2 \
    gcode_file:=/tmp/chair.gcode

# 6. Start a print
ros2 service call /print_node/start_print ur_3d_printer/srv/StartPrint \
    "{gcode_filepath: '/tmp/chair.gcode'}"
```

---

## Architecture

```
G-code file
    │
    ▼
GCodeParser          Parses G0/G1/G2/G3/M104/M106 into Waypoints + Layers
    │
    ▼
WorkspaceValidator   Checks reach radius, singularity threshold, bounding box
    │
    ▼
TrajectoryPlanner    IK per waypoint (screw-theory LM solver)
    │  z-hop on travel moves, joint-jump detection, per-joint velocity limits
    │
    ▼
VelocityProfiler     Trapezoidal velocity profile → time-stamps each waypoint
    │
    ▼
JointTrajectory      Sent via FollowJointTrajectory action to:
    │                  - mock_controller (standalone)
    │                  - ur_robot_driver  (URSim / real robot)
    ▼
Robot moves          TF published → robot_state_publisher → RViz
```

### Nodes

| Node | Description |
|------|-------------|
| `print_node` | State machine: IDLE → PRINTING → PAUSED → DONE |
| `extruder_controller` | Simulates FDM extruder temperature and extrusion |
| `toolpath_visualizer` | Publishes colored `MarkerArray` of the toolpath |
| `mock_controller` | Standalone only: serves `FollowJointTrajectory`, replays as `/joint_states` |
| `ur_kinematics_server` | IK/FK/Jacobian services (from `ur_kinematics_node`) |

### Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/print_node/state` | `PrintState` | Current state + error message |
| `/print_node/progress` | `PrintProgress` | Layer, overall %, elapsed time |
| `/toolpath_visualizer/markers` | `MarkerArray` | Toolpath line strips in RViz |
| `/joint_states` | `JointState` | Robot joint positions |
| `/extruder_controller/extruder_state` | `ExtruderState` | Temperature, flow rate |

### Services

| Service | Type | Description |
|---------|------|-------------|
| `/print_node/start_print` | `StartPrint` | Load G-code and start printing |
| `/print_node/pause_print` | `PausePrint` | Pause at end of current trajectory |
| `/print_node/resume_print` | `ResumePrint` | Resume from paused state |
| `/print_node/cancel_print` | `CancelPrint` | Abort and return to idle |
| `/print_node/calibrate_origin` | `CalibrateOrigin` | Set print origin from current TCP pose |

---

## G-code Generation

Any standard FDM slicer works (PrusaSlicer, Cura, etc). A minimal numpy-only
STL slicer is included for quick testing:

```bash
# Slice STL to G-code
python3 workspace/src/ur_3d_printer/resource/stl_slicer.py \
    my_model.stl \
    --output my_model.gcode \
    --layer-height 0.2 \
    --nozzle 0.4 \
    --print-speed 2400

# The included chair demo
python3 workspace/src/ur_3d_printer/resource/stl_slicer.py \
    workspace/src/ur_3d_printer/resource/chair.stl \
    -o /tmp/chair.gcode
# → 76 layers, 22 595 waypoints, ~18.6 min at 50 mm/s
```

---

## Configuration — `config/print_params.yaml`

### Print origin

```yaml
print_node:
  ros__parameters:
    print_origin_xyz: [0.4, 0.0, 0.92]   # G-code (0,0,0) in robot base frame (m)
    print_origin_rpy: [3.14159, 0.0, 0.0] # Rotation: π around X = nozzle points down
    tool_offset_xyz:  [0.0, 0.0, 0.15]    # Flange → nozzle tip (m)
```

### Motion

```yaml
    max_print_velocity:  0.05   # m/s  — extrusion moves
    max_travel_velocity: 0.15   # m/s  — non-extrusion moves
    max_acceleration:    0.5    # m/s²
    waypoint_density:    0.002  # m    — max segment length for IK densification
```

### Arm-robot specific

```yaml
    # Z-hop on travel moves (arm paths are curved, not straight lines)
    z_hop_enabled: true
    z_hop_height:  0.005        # 5 mm lift before each travel move

    # Joint-jump guard (detects IK branch switches = dangerous motion)
    max_joint_jump: 0.5         # rad — reject IK solution if any joint moves more

    # Per-joint hardware velocity limits
    joint_velocity_limits: [3.14, 3.14, 3.14, 3.14, 3.14, 3.14]  # rad/s

    # Singularity avoidance (minimum Jacobian singular value)
    singularity_threshold:      0.05   # approach → slow down
    singularity_velocity_scale: 0.3    # scale velocity to this fraction near singularity

    # Radial reach envelope
    min_reach_radius: 0.17      # m — inner dead zone (shoulder singularity)
    max_reach_radius: 0.85      # m — maximum arm reach

    # IK solver
    ik_method:         lm       # Levenberg-Marquardt
    ik_max_iterations: 100
    ik_tolerance:      1.0e-6
    ik_timeout:        5.0      # seconds per waypoint

    # Bed tilt compensation (correct a tilted print surface without re-slicing)
    bed_tilt_rx: 0.0            # rad — rotation around X
    bed_tilt_ry: 0.0            # rad — rotation around Y

    # Preferred arm configuration (sets IK seed to stay in this branch)
    preferred_arm_config: elbow_up   # or elbow_down
```

---

## Package Structure

```
ur_3d_printer/
├── config/
│   ├── print_params.yaml           # All node parameters
│   └── printer_3d.rviz             # RViz layout
├── launch/
│   ├── print_standalone.launch.py  # Standalone (mock controller)
│   ├── print_ursim.launch.py       # App nodes only (driver external)
│   ├── print_driver.launch.py      # Full driver integration
│   └── ur_3d_printer_rsp.launch.py # RSP description for ur_control
├── msg/
│   ├── PrintState.msg
│   └── PrintProgress.msg
├── srv/
│   ├── StartPrint.srv
│   ├── PausePrint.srv
│   ├── ResumePrint.srv
│   ├── CancelPrint.srv
│   ├── CalibrateOrigin.srv
│   └── SetExtruder.srv
├── action/
│   └── ExecutePrint.action
├── urdf/
│   ├── ur_3d_printer_cell.urdf.xacro   # Full workcell (for ur_robot_driver)
│   ├── printer_standalone.urdf.xacro   # Simplified standalone scene
│   ├── fdm_extruder.urdf.xacro
│   ├── paste_extruder.urdf.xacro
│   └── print_bed.urdf.xacro
├── ur_3d_printer/
│   ├── print_node.py           # Main state machine
│   ├── gcode_parser.py         # G0/G1/G2/G3 parser
│   ├── toolpath.py             # Waypoint / Layer / Toolpath data classes
│   ├── trajectory_planner.py   # IK + velocity profiling
│   ├── workspace_validator.py  # Pre-print safety checks
│   ├── velocity_profiler.py    # Trapezoidal velocity profile
│   ├── extruder_controller.py  # FDM extruder simulation
│   ├── toolpath_visualizer.py  # RViz MarkerArray publisher
│   └── mock_controller.py      # Standalone trajectory replayer
├── resource/
│   ├── stl_slicer.py           # Minimal numpy STL → G-code slicer
│   └── chair.stl               # Demo model (21 760 triangles)
└── test/
    ├── test_gcode_parser.py        # 15 tests
    ├── test_toolpath.py            # 17 tests
    ├── test_trajectory_planner.py  # 13 tests
    └── test_workspace_validator.py #  7 tests
```

---

## Running Tests

```bash
colcon test --packages-select ur_3d_printer
colcon test-result --test-result-base build/ur_3d_printer --all
# Expected: 104 tests, 0 failures
```
