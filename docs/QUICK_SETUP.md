# URSim + ROS2 External Control - Quick Setup Guide

> Fast-track guide to connect ROS2 with Universal Robots simulator

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Docker | 20.10+ |
| ROS2 | Humble |
| ur_robot_driver | 2.11.0+ |

---

## Step 1: Create Directories

```bash
mkdir -p ${HOME}/.ursim/programs
mkdir -p ${HOME}/.ursim/urcaps
```

---

## Step 2: Download External Control URCap

```bash
URCAP_VERSION=1.0.5
curl -L -o ${HOME}/.ursim/urcaps/externalcontrol-${URCAP_VERSION}.jar \
  https://github.com/UniversalRobots/Universal_Robots_ExternalControl_URCap/releases/download/v${URCAP_VERSION}/externalcontrol-${URCAP_VERSION}.jar
```

---

## Step 3: Start URSim Container

```bash
docker run --rm -it \
  -p 5900:5900 \
  -p 6080:6080 \
  -p 29999:29999 \
  -p 30001:30001 \
  -p 30002:30002 \
  -p 30003:30003 \
  -p 30004:30004 \
  -v ${HOME}/.ursim/urcaps:/urcaps \
  -v ${HOME}/.ursim/programs:/ursim/programs \
  -e ROBOT_MODEL=UR5 \
  --name ursim \
  universalrobots/ursim_e-series
```

---

## Step 4: Configure External Control in URSim

1. Open URSim web interface: http://localhost:6080
2. Power on the robot (red button → Power On → Start)
3. Go to **Installation → URCaps → External Control**
4. Set **Host IP**: `172.17.0.1` (Docker host)
5. Set **Port**: `50002`
6. Save installation

---

## Step 5: Create Robot Program

1. Go to **Program → Empty Program**
2. Add **URCaps → External Control** node
3. Save as `external_control.urp`

---

## Step 6: Launch ROS2 Driver

```bash
ros2 launch ur_robot_driver ur_control.launch.py \
  ur_type:=ur5e \
  robot_ip:=172.17.0.2 \
  headless_mode:=true \
  launch_rviz:=true \
  initial_joint_controller:=joint_trajectory_controller
```

> **Note**: Use `initial_joint_controller:=joint_trajectory_controller` to avoid segfault issues with scaled controller in version 2.11.0

---

## Step 7: Run External Control Program

1. In URSim, load `external_control.urp`
2. Press **Play**
3. Robot should connect to ROS2 driver

---

## Step 8: Test Motion Command

```bash
ros2 action send_goal /joint_trajectory_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory "{
    trajectory: {
      joint_names: [shoulder_pan_joint, shoulder_lift_joint, elbow_joint,
                    wrist_1_joint, wrist_2_joint, wrist_3_joint],
      points: [
        { positions: [0.0, -1.57, 1.57, -1.57, -1.57, 0.0], time_from_start: { sec: 5 } }
      ]
    }
  }"
```

---

## Verification Checklist

- [ ] URSim container running
- [ ] Robot powered on (green status)
- [ ] ROS2 driver launched without errors
- [ ] External Control program running
- [ ] `/joint_states` topic publishing
- [ ] RViz showing robot model
- [ ] Motion commands execute successfully

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Connection refused on port 50002 | Ensure ROS2 driver is running before starting External Control program |
| Driver segfault | Use `initial_joint_controller:=joint_trajectory_controller` |
| ROS2 daemon not responding | Run `pkill -9 ros2_daemon && rm -rf ~/.ros/ros2d*` |
| Can't find robot IP | Run `docker inspect ursim --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'` |

---

## Quick Reference

| Component | Address |
|-----------|---------|
| URSim Container | 172.17.0.2 |
| Docker Host (for robot) | 172.17.0.1 |
| External Control Port | 50002 |
| Web VNC | http://localhost:6080 |
| Dashboard | localhost:29999 |
