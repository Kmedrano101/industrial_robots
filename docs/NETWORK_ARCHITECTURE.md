# Network Architecture & Communication Guide

> Comprehensive documentation of the URSim + ROS2 network topology

---

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              HOST MACHINE                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                         ROS2 Environment                              │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │  │
│  │  │  ur_robot_driver │  │     RViz2       │  │  Your ROS2 App  │       │  │
│  │  │   172.17.0.1    │  │   Visualization │  │    (Optional)   │        │  │
│  │  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘        │  │
│  │           │                    │                    │                 │  │
│  │           └────────────────────┴────────────────────┘                 │  │
│  │                                │                                      │  │
│  │                         ROS2 Topics                                   │  │
│  │                    /joint_states, /tf, etc.                           │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                   │                                         │
│                          docker0: 172.17.0.1                                │
│  ─────────────────────────────────┼──────────────────────────────────────── │
│                                   │                                         │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      Docker Container: ursim                          │  │
│  │                         IP: 172.17.0.2                                │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │                    URSim (e-Series)                             │  │  │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │  │  │
│  │  │  │  PolyScope  │  │   URCaps    │  │   Robot Controller      │  │  │  │
│  │  │  │     GUI     │  │  External   │  │   Primary/Secondary     │  │  │  │
│  │  │  │             │  │   Control   │  │   RTDE Interfaces       │  │  │  │
│  │  │  └─────────────┘  └─────────────┘  └─────────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Network Interfaces

### Host Machine

| Interface | IP Address | Purpose |
|-----------|------------|---------|
| `docker0` | 172.17.0.1 | Docker bridge network gateway |
| `lo` | 127.0.0.1 | Loopback interface |
| `eno2` / `eth0` | DHCP assigned | Physical network |

### Docker Container (URSim)

| Interface | IP Address | Purpose |
|-----------|------------|---------|
| `eth0` | 172.17.0.2 | Container network interface |

---

## Port Mapping Reference

### Robot Communication Ports

| Port | Protocol | Direction | Service | Description |
|------|----------|-----------|---------|-------------|
| **29999** | TCP | Host → Robot | Dashboard Server | Robot control commands, power on/off, load programs |
| **30001** | TCP | Host → Robot | Primary Interface | Robot state data (10 Hz) |
| **30002** | TCP | Host → Robot | Secondary Interface | Robot state + URScript commands (10 Hz) |
| **30003** | TCP | Host → Robot | Real-Time Interface | Real-time robot state (125 Hz) |
| **30004** | TCP | Bidirectional | RTDE Interface | Real-Time Data Exchange (500 Hz) |

### External Control Ports

| Port | Protocol | Direction | Service | Description |
|------|----------|-----------|---------|-------------|
| **50001** | TCP | Robot → Host | Script Command | URScript command interface |
| **50002** | TCP | Robot → Host | Reverse Interface | Trajectory forwarding from ROS2 |
| **50003** | TCP | Robot → Host | Trajectory Port | Trajectory point streaming |
| **50004** | TCP | Robot → Host | Script State | Script execution state |

### Visualization Ports

| Port | Protocol | Service | Description |
|------|----------|---------|-------------|
| **5900** | TCP | VNC Server | Direct VNC connection to URSim |
| **6080** | TCP | noVNC (Web) | Browser-based VNC access |

---

## Communication Flow

### Initialization Sequence

```
Step 1: Container Start
========================
[Docker Engine] ──creates──> [ursim container @ 172.17.0.2]
                                      │
                                      ▼
                              [URSim boots up]
                              [Opens ports 29999, 30001-30004]

Step 2: ROS2 Driver Launch
==========================
[ur_robot_driver] ──connects──> [172.17.0.2:30001-30004]
        │                              │
        │                              ▼
        │                       [State streaming begins]
        │
        └──opens──> [Reverse interface on 172.17.0.1:50002]

Step 3: External Control Program
================================
[URSim Program] ──runs──> [ExternalControl URCap]
                                   │
                                   ▼
                          [Connects to 172.17.0.1:50002]
                                   │
                                   ▼
                          [Bidirectional control established]
```

### Data Flow During Operation

```
┌─────────────────┐                              ┌─────────────────┐
│   ROS2 Driver   │                              │     URSim       │
│  (172.17.0.1)   │                              │  (172.17.0.2)   │
└────────┬────────┘                              └────────┬────────┘
         │                                                │
         │  ◄────── Joint States (RTDE :30004) ───────────│
         │         Position, Velocity, Effort             │
         │         @ 500 Hz                               │
         │                                                │
         │  ◄────── Robot Mode/Status (:30001) ───────────│
         │         Safety state, program state            │
         │         @ 10 Hz                                │
         │                                                │
         │  ─────── Trajectory Commands (:50002) ────────►│
         │         Joint positions, velocities            │
         │         @ 125 Hz (servo rate)                  │
         │                                                │
         │  ─────── URScript Commands (:50001) ──────────►│
         │         Direct script execution                │
         │                                                │
         ▼                                                ▼
┌─────────────────┐                              ┌─────────────────┐
│  /joint_states  │                              │  Robot Motion   │
│  /tf            │                              │  Execution      │
│  /wrench        │                              │                 │
└─────────────────┘                              └─────────────────┘
```

---

## IP Address Configuration

### Why 172.17.0.1?

The IP `172.17.0.1` is the **Docker bridge gateway**. When a container needs to reach a service running on the host machine, it connects to this address.

```
┌──────────────────────────────────────────────────────┐
│                    HOST (Linux)                      │
│                                                      │
│   ┌─────────────────┐      ┌─────────────────┐       │
│   │   ROS2 Driver   │      │  docker0 bridge │       │
│   │  Listens on     │◄────►│   172.17.0.1    │       │
│   │  0.0.0.0:50002  │      │                 │       │
│   └─────────────────┘      └────────┬────────┘       │
│                                     │                │
└─────────────────────────────────────┼────────────────┘
                                      │
                            ┌─────────▼─────────┐
                            │  Docker Network   │
                            │   172.17.0.0/16   │
                            └─────────┬─────────┘
                                      │
                            ┌─────────▼─────────┐
                            │  URSim Container  │
                            │    172.17.0.2     │
                            │                   │
                            │  Connects to:     │
                            │  172.17.0.1:50002 │
                            └───────────────────┘
```

### Finding the Correct IP

```bash
# Get Docker bridge IP (host side)
ip addr show docker0 | grep "inet " | awk '{print $2}' | cut -d/ -f1

# Get container IP
docker inspect ursim --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
```

---

## ROS2 Topics Reference

### Published by ur_robot_driver

| Topic | Type | Frequency | Description |
|-------|------|-----------|-------------|
| `/joint_states` | sensor_msgs/JointState | 500 Hz | Joint positions, velocities, efforts |
| `/tf` | tf2_msgs/TFMessage | 500 Hz | Transform tree |
| `/tf_static` | tf2_msgs/TFMessage | Latched | Static transforms |
| `/force_torque_sensor_broadcaster/wrench` | geometry_msgs/WrenchStamped | 500 Hz | TCP force/torque |
| `/io_and_status_controller/robot_mode` | ur_msgs/RobotMode | 10 Hz | Current robot mode |
| `/io_and_status_controller/safety_mode` | ur_msgs/SafetyMode | 10 Hz | Safety system state |
| `/io_and_status_controller/io_states` | ur_msgs/IOStates | 10 Hz | Digital/analog I/O |

### Subscribed by ur_robot_driver

| Topic | Type | Description |
|-------|------|-------------|
| `/urscript_interface/script_command` | std_msgs/String | Direct URScript execution |

### Action Servers

| Action | Type | Description |
|--------|------|-------------|
| `/joint_trajectory_controller/follow_joint_trajectory` | control_msgs/FollowJointTrajectory | Trajectory execution |
| `/freedrive_mode_controller/enable_freedrive_mode` | std_srvs/Trigger | Enable freedrive |

---

## Security Considerations

### Network Isolation

| Risk | Mitigation |
|------|------------|
| Unauthorized robot control | Use Docker network isolation, don't expose ports to 0.0.0.0 |
| Dashboard command injection | Limit dashboard port (29999) access |
| URScript injection | Validate all script commands |

### Recommended Firewall Rules

```bash
# Allow only local access to robot ports
iptables -A INPUT -p tcp --dport 29999 -s 127.0.0.1 -j ACCEPT
iptables -A INPUT -p tcp --dport 29999 -s 172.17.0.0/16 -j ACCEPT
iptables -A INPUT -p tcp --dport 29999 -j DROP
```

---

## Troubleshooting Network Issues

### Diagnostic Commands

```bash
# Check if URSim ports are accessible
nc -zv 172.17.0.2 30001
nc -zv 172.17.0.2 30004
nc -zv 172.17.0.2 29999

# Check if reverse interface is listening
ss -tlnp | grep 50002

# Test dashboard connection
echo "robotmode" | nc 172.17.0.2 29999

# Check ROS2 topics
ros2 topic list
ros2 topic hz /joint_states
```

### Common Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| "Connection refused" on 50002 | Driver not ready | Wait for driver to fully initialize |
| No joint states | RTDE connection failed | Check port 30004 connectivity |
| Robot doesn't move | External Control not running | Start program in URSim |
| Intermittent disconnects | Network latency | Use `ROS_LOCALHOST_ONLY=1` |

---

## Performance Tuning

### Real-Time Performance

```bash
# Check if RT kernel is available
uname -a | grep -i rt

# Set process priority (requires sudo)
sudo chrt -f 99 $(pgrep ur_ros2_control)

# Disable CPU frequency scaling
sudo cpupower frequency-set -g performance
```

### Network Optimization

```bash
# Increase socket buffer sizes
sudo sysctl -w net.core.rmem_max=16777216
sudo sysctl -w net.core.wmem_max=16777216

# Reduce latency for Docker bridge
sudo tc qdisc replace dev docker0 root pfifo_fast
```

---

## Reference Diagram

```
    ┌─────────────────────────────────────────────────────────────────┐
    │                        NETWORK TOPOLOGY                         │
    └─────────────────────────────────────────────────────────────────┘

                           Internet/LAN
                                │
                    ┌───────────┴───────────┐
                    │     Host Machine      │
                    │    (Your PC/Server)   │
                    │                       │
                    │  ┌─────────────────┐  │
                    │  │   eno2/eth0     │  │
                    │  │ 192.168.1.130   │  │
                    │  └────────┬────────┘  │
                    │           │           │
                    │  ┌────────┴────────┐  │
                    │  │   Loopback      │  │
                    │  │   127.0.0.1     │  │
                    │  └────────┬────────┘  │
                    │           │           │
                    │  ┌────────┴────────┐  │
                    │  │   docker0       │──┼──────────┐
                    │  │   172.17.0.1    │  │          │
                    │  └─────────────────┘  │          │
                    │                       │          │
                    │  ┌─────────────────┐  │          │
                    │  │  ROS2 Nodes     │  │          │
                    │  │  • ur_driver    │  │          │
                    │  │  • rviz2        │  │          │
                    │  │  • your_app     │  │          │
                    │  └─────────────────┘  │          │
                    └───────────────────────┘          │
                                                       │
                              Docker Bridge Network    │
                              ─────────────────────────┼─────
                                                       │
                    ┌───────────────────────┐          │
                    │   Docker Container    │          │
                    │       "ursim"         │◄─────────┘
                    │                       │
                    │  ┌─────────────────┐  │
                    │  │     eth0        │  │
                    │  │   172.17.0.2    │  │
                    │  └─────────────────┘  │
                    │                       │
                    │  ┌─────────────────┐  │
                    │  │     URSim       │  │
                    │  │   e-Series      │  │
                    │  │   Simulator     │  │
                    │  └─────────────────┘  │
                    │                       │
                    │  Exposed Ports:       │
                    │  • 5900  (VNC)        │
                    │  • 6080  (Web VNC)    │
                    │  • 29999 (Dashboard)  │
                    │  • 30001 (Primary)    │
                    │  • 30002 (Secondary)  │
                    │  • 30003 (RT)         │
                    │  • 30004 (RTDE)       │
                    └───────────────────────┘
```

---

*Document Version: 1.0*
*Last Updated: January 2026*
