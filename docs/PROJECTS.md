# Projects

This document contains example projects and applications built with the Industrial Robots framework.

---

## Project 1: UR Pick and Place Workcell

A complete pick and place demonstration using a UR5e robot with a custom workcell including an industrial table, parallel gripper, and colored objects.

![UR Pick and Place Workcell](images/project_1.png)

### Description

This project demonstrates a typical industrial pick and place application:

- **UR5e Robot Arm** - 6-DOF collaborative robot
- **Industrial Table** - 1.0m x 0.7m work surface with robot mount
- **Parallel Gripper** - Two-finger gripper attached to tool flange
- **Pick Objects** - Three colored cubes (red, green, blue) at pick location (A)
- **Place Markers** - Three yellow markers at place location (B)

The robot picks objects from location A and places them at location B, demonstrating basic motion planning and gripper control.

### Package Structure

```
workspace/src/ur_pick_place/
├── config/
│   ├── pick_place.yaml      # Node configuration
│   └── pick_place.rviz      # RViz visualization config
├── launch/
│   ├── ur_pick_place_driver.launch.py   # Main launch file
│   └── ur_pick_place_rsp.launch.py      # Robot state publisher
├── urdf/
│   ├── ur_pick_place_cell.urdf.xacro    # Complete workcell URDF
│   ├── parallel_gripper.urdf.xacro      # Gripper description
│   └── industrial_table.urdf.xacro      # Table description
└── ur_pick_place/
    ├── pick_place_node.py    # Pick and place logic
    └── gripper_controller.py # Gripper control node
```

### Prerequisites

1. **URSim Running** - Start the UR simulator in Docker:
   ```bash
   docker run -d --rm \
       -p 5900:5900 -p 6080:6080 -p 29999:29999 -p 30001-30004:30001-30004 \
       -e ROBOT_MODEL=UR5 \
       --name ursim \
       universalrobots/ursim_e-series
   ```

2. **ROS2 Jazzy** - Install ROS2 and ur_robot_driver:
   ```bash
   sudo apt install ros-jazzy-ur-robot-driver
   ```

3. **Build the Package**:
   ```bash
   cd ~/src/industrial_robots/workspace
   source /opt/ros/jazzy/setup.bash
   colcon build --packages-select ur_pick_place --symlink-install
   ```

### Running the Project

1. **Start URSim** and wait for it to reach "Normal" state (access via http://localhost:6080)

2. **Power ON the Robot** in URSim:
   - Click the red power button
   - Click "ON" then "START"
   - Robot should show "Normal" status

3. **Launch the Driver with Workcell**:
   ```bash
   source /opt/ros/jazzy/setup.bash
   source ~/src/industrial_robots/workspace/install/setup.bash
   ros2 launch ur_pick_place ur_pick_place_driver.launch.py robot_ip:=172.17.0.2 headless_mode:=true
   ```

4. **Configure External Control in URSim**:
   - Go to Installation → URCaps → External Control
   - Set Host IP to your machine's IP (run `hostname -I` to find it)
   - Create a new program with External Control node
   - Press PLAY

5. **RViz** will automatically open showing the workcell with robot, table, gripper, and objects.

### Launch Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `robot_ip` | `172.17.0.2` | IP address of URSim or real robot |
| `ur_type` | `ur5e` | Robot model (ur3e, ur5e, ur10e, etc.) |
| `headless_mode` | `true` | Run without teach pendant |
| `launch_rviz` | `true` | Launch RViz visualization |
| `include_gripper` | `true` | Include gripper in URDF |
| `include_objects` | `true` | Include pick/place objects |

### Services

| Service | Type | Description |
|---------|------|-------------|
| `/pick_place_node/pick_place` | `PickPlace` | Execute pick and place cycle |
| `/gripper_controller/set_gripper` | `SetGripper` | Open/close gripper |

### Example Commands

```bash
# Execute pick and place
ros2 service call /pick_place_node/pick_place ur_pick_place/srv/PickPlace "{}"

# Open gripper
ros2 service call /gripper_controller/set_gripper ur_pick_place/srv/SetGripper "{open: true}"

# Close gripper
ros2 service call /gripper_controller/set_gripper ur_pick_place/srv/SetGripper "{open: false}"

# Check joint states
ros2 topic echo /joint_states
```

### Configuration

Edit `config/pick_place.yaml` to customize positions:

```yaml
pick_place_node:
  ros__parameters:
    pick_position: [0.20, 0.15, 0.92]   # Pick location (x, y, z)
    place_position: [0.20, -0.15, 0.92] # Place location (x, y, z)
    approach_height: 0.15               # Height above object for approach
    object_height: 0.04                 # Object height for grasp calculation
```

---

## Project 2: UR 3D Printer

A ROS2 package that turns any Universal Robots arm (UR3e–UR30) into a 3D printer.
G-code is parsed, converted to Cartesian waypoints, solved through screw-theory IK,
and streamed to the robot as `JointTrajectory` messages — all in real-time.

### Description

This project demonstrates advanced trajectory generation and real-time motion control:

- **G-code Support** — Standard FDM slicer output (PrusaSlicer, Cura, etc.)
- **Screw-Theory IK** — Levenberg-Marquardt solver with seed chaining for smooth motion
- **Trapezoidal Velocity Profiles** — Singularity-aware speed scaling, corner blending
- **FDM / Paste Extruder Simulation** — Temperature, flow rate, retraction
- **Three Launch Modes** — Standalone (no robot), URSim, real robot

### Quick Start (Standalone — no robot needed)

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

### Package Structure

```
workspace/src/ur_3d_printer/
├── config/
│   ├── print_params.yaml           # All node parameters
│   └── printer_3d.rviz             # RViz layout
├── launch/
│   ├── print_standalone.launch.py  # Standalone (mock controller)
│   ├── print_ursim.launch.py       # App nodes only (driver external)
│   └── print_driver.launch.py      # Full driver integration
├── msg/
│   ├── PrintState.msg
│   └── PrintProgress.msg
├── srv/
│   ├── StartPrint.srv
│   ├── PausePrint.srv
│   ├── ResumePrint.srv
│   ├── CancelPrint.srv
│   └── CalibrateOrigin.srv
├── urdf/
│   ├── ur_3d_printer_cell.urdf.xacro   # Full workcell
│   ├── printer_standalone.urdf.xacro   # Simplified standalone scene
│   ├── fdm_extruder.urdf.xacro
│   └── print_bed.urdf.xacro
└── ur_3d_printer/
    ├── print_node.py           # Main state machine
    ├── gcode_parser.py         # G0/G1/G2/G3 parser
    ├── trajectory_planner.py   # IK + velocity profiling
    ├── workspace_validator.py  # Pre-print safety checks
    ├── velocity_profiler.py    # Trapezoidal velocity profile
    ├── extruder_controller.py  # FDM extruder simulation
    ├── toolpath_visualizer.py  # RViz MarkerArray publisher
    └── mock_controller.py      # Standalone trajectory replayer
```

### Prerequisites

1. **ROS2 Jazzy** with `ur_robot_driver`:
   ```bash
   sudo apt install ros-jazzy-ur-robot-driver
   ```

2. **Build the packages**:
   ```bash
   cd ~/src/industrial_robots/workspace
   source /opt/ros/jazzy/setup.bash
   colcon build --packages-select ur_3d_printer ur_kinematics_node \
                ur_screw_kinematics ur_kinematics_msgs --symlink-install
   source install/setup.bash
   ```

### Launch Modes

| Mode | Launch file | When to use |
|------|-------------|-------------|
| **Standalone** | `print_standalone.launch.py` | Development, no robot or URSim needed |
| **URSim app** | `print_ursim.launch.py` | Driver already running (e.g. in Docker) |
| **Full driver** | `print_driver.launch.py` | One-command bring-up against URSim or real robot |

### URSim Setup

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
ros2 launch ur_3d_printer print_driver.launch.py \
    robot_ip:=172.17.0.2 \
    gcode_file:=/tmp/chair.gcode

# 6. Start a print
ros2 service call /print_node/start_print ur_3d_printer/srv/StartPrint \
    "{gcode_filepath: '/tmp/chair.gcode'}"
```

### Launch Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `gcode_file` | `''` | G-code file to preload for toolpath visualization |
| `speed_scale` | `1.0` | Playback speed multiplier (standalone only) |
| `robot_model` | `ur5e` | UR robot model |
| `robot_ip` | `172.17.0.2` | IP of URSim or real robot (driver mode) |
| `ur_type` | `ur5e` | Robot type (driver mode) |
| `launch_rviz` | `true` | Open RViz |

### Services

| Service | Type | Description |
|---------|------|-------------|
| `/print_node/start_print` | `StartPrint` | Load G-code and start printing |
| `/print_node/pause_print` | `PausePrint` | Pause at end of current trajectory |
| `/print_node/resume_print` | `ResumePrint` | Resume from paused state |
| `/print_node/cancel_print` | `CancelPrint` | Abort and return to idle |
| `/print_node/calibrate_origin` | `CalibrateOrigin` | Set print origin from current TCP pose |

### Example Commands

```bash
# Slice included chair model
python3 workspace/src/ur_3d_printer/resource/stl_slicer.py \
    workspace/src/ur_3d_printer/resource/chair.stl \
    -o /tmp/chair.gcode
# → 76 layers, 22 595 waypoints

# Start standalone demo
ros2 launch ur_3d_printer print_standalone.launch.py \
    gcode_file:=/tmp/chair.gcode speed_scale:=10.0

# Start a print
ros2 service call /print_node/start_print ur_3d_printer/srv/StartPrint \
    "{gcode_filepath: '/tmp/chair.gcode'}"

# Pause mid-print
ros2 service call /print_node/pause_print ur_3d_printer/srv/PausePrint "{}"

# Resume
ros2 service call /print_node/resume_print ur_3d_printer/srv/ResumePrint "{}"

# Monitor progress
ros2 topic echo /print_node/progress
```

### Configuration

Edit `config/print_params.yaml` to customize the print origin and motion parameters:

```yaml
print_node:
  ros__parameters:
    # Print origin (G-code 0,0,0 in robot base frame)
    print_origin_xyz: [0.4, 0.0, 0.92]   # meters
    print_origin_rpy: [3.14159, 0.0, 0.0] # nozzle points down

    # Motion limits
    max_print_velocity:  0.05   # m/s  — extrusion moves
    max_travel_velocity: 0.15   # m/s  — travel moves
    max_acceleration:    0.5    # m/s²
    waypoint_density:    0.002  # m    — max segment length

    # Arm-robot safety
    z_hop_enabled: true
    z_hop_height:  0.005        # 5 mm lift before travel
    max_joint_jump: 0.5         # rad — IK branch guard
    singularity_threshold: 0.05
    min_reach_radius: 0.17      # m
    max_reach_radius: 0.85      # m
```

### Running Tests

```bash
colcon test --packages-select ur_3d_printer
colcon test-result --test-result-base build/ur_3d_printer --all
# Expected: 104 tests, 0 failures
```

For full documentation see [`workspace/src/ur_3d_printer/README.md`](../workspace/src/ur_3d_printer/README.md).

---

## More Projects Coming Soon

- **Vision-Based Sorting** - Camera integration for object detection
- **Palletizing Demo** - Multi-layer stacking patterns
- **Conveyor Tracking** - Synchronized motion with moving objects
