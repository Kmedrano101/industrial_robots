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

## More Projects Coming Soon

- **Vision-Based Sorting** - Camera integration for object detection
- **Palletizing Demo** - Multi-layer stacking patterns
- **Conveyor Tracking** - Synchronized motion with moving objects
