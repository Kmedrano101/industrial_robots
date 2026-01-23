# Docker Architecture for UR + ROS2

> Portable, Multi-Version ROS2 Integration with Universal Robots

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           Docker Compose Stack                             │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                        ur-network (172.28.0.0/16)                     │ │
│  │                                                                       │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │ │
│  │  │     ursim       │  │    ur-driver    │  │     rviz        │        │ │
│  │  │  172.28.0.10    │  │   172.28.0.20   │  │   (optional)    │        │ │
│  │  │                 │  │                 │  │                 │        │ │
│  │  │  URSim e-Series │  │  ROS2 Driver    │  │  Visualization  │        │ │
│  │  │  + ExternalCtrl │  │  (any distro)   │  │                 │        │ │
│  │  └────────┬────────┘  └────────┬────────┘  └─────────────────┘        │ │
│  │           │                    │                                      │ │
│  │           └────────────────────┘                                      │ │
│  │                    Robot Communication                                │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  Exposed to Host:                                                          │
│  • 5900  (VNC)         • 30001 (Primary)      • 30003 (RT)                 │
│  • 6080  (Web VNC)     • 30002 (Secondary)    • 30004 (RTDE)               │
│  • 29999 (Dashboard)                                                       │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
robots/
├── docker-compose.yml          # Main orchestration file
├── .env.example                 # Configuration template
├── .env                         # Your configuration (git-ignored)
│
├── docker/
│   ├── ros2-driver/
│   │   ├── Dockerfile          # Multi-version ROS2 driver image
│   │   └── entrypoint.sh       # Startup script
│   │
│   ├── ursim/
│   │   └── Dockerfile          # URSim with ExternalControl
│   │
│   └── scripts/
│       ├── build.sh            # Build images
│       ├── start.sh            # Start stack
│       ├── stop.sh             # Stop stack
│       └── status.sh           # Check status
│
├── config/
│   └── calibration/            # Robot calibration files
│
├── programs/                    # URSim programs
│
├── workspace/                   # ROS2 development workspace
│
└── docs/
    ├── QUICK_SETUP.md
    ├── NETWORK_ARCHITECTURE.md
    └── DOCKER_ARCHITECTURE.md
```

---

## Supported ROS2 Distributions

| Distribution | Status | Base Image | EOL |
|--------------|--------|------------|-----|
| **Humble** | LTS | `osrf/ros:humble-desktop` | May 2027 |
| **Iron** | Stable | `osrf/ros:iron-desktop` | Nov 2024 |
| **Jazzy** | LTS | `osrf/ros:jazzy-desktop` | May 2029 |
| **Rolling** | Dev | `osrf/ros:rolling-desktop` | Continuous |

### Switching ROS2 Versions

```bash
# Build for specific version
ROS_DISTRO=jazzy ./docker/scripts/build.sh

# Or set in .env file
echo "ROS_DISTRO=jazzy" >> .env

# Or inline with docker compose
ROS_DISTRO=jazzy docker compose --profile sim up
```

---

## Profiles

| Profile | Services Started | Use Case |
|---------|------------------|----------|
| `sim` | ursim, ur-driver | Simulation development |
| `real` | ur-driver | Real robot control |
| `viz` | rviz | Visualization only |
| `dev` | ros2-dev | Development shell |
| `full` | All services | Complete environment |

### Usage Examples

```bash
# Simulation mode
docker compose --profile sim up

# Real robot mode
ROBOT_IP=192.168.1.100 docker compose --profile real up

# Development shell
docker compose --profile dev run --rm ros2-dev

# Full stack with visualization
docker compose --profile full up
```

---

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `ROS_DISTRO` | humble | ROS2 distribution |
| `ROS_DOMAIN_ID` | 0 | DDS domain isolation |
| `ROBOT_IP` | 172.28.0.10 | Robot IP address |
| `UR_TYPE` | ur5e | Robot type for driver |
| `ROBOT_MODEL` | UR5 | Robot model for URSim |
| `HEADLESS_MODE` | true | Skip URCap installation prompt |

### Real Robot Configuration

```bash
# .env for real robot
ROS_DISTRO=humble
ROBOT_IP=192.168.1.100    # Your robot's IP
UR_TYPE=ur10e             # Your robot type
```

---

## Services Detail

### URSim Service

```yaml
ursim:
  image: ur-ursim:latest
  networks:
    ur-network:
      ipv4_address: 172.28.0.10
  ports:
    - "5900:5900"    # VNC
    - "6080:6080"    # Web VNC
    - "29999:29999"  # Dashboard
    - "30001-30004"  # Robot interfaces
```

**Features:**
- Pre-installed ExternalControl URCap
- Configurable robot model
- Health check for readiness
- Persistent URCap volume

### UR Driver Service

```yaml
ur-driver:
  image: ur-ros2-driver:${ROS_DISTRO}
  networks:
    ur-network:
      ipv4_address: 172.28.0.20
  depends_on:
    ursim:
      condition: service_healthy
```

**Features:**
- Multi-ROS2 version support
- Auto-waits for robot availability
- Configurable controller selection
- X11 forwarding for GUI tools

---

## Networking

### Custom Bridge Network

```
┌─────────────────────────────────────────────┐
│           ur-network (172.28.0.0/16)        │
│                                             │
│  Gateway: 172.28.0.1                        │
│                                             │
│  ┌─────────────┐      ┌─────────────┐       │
│  │   ursim     │      │  ur-driver  │       │
│  │ 172.28.0.10 │◄────►│ 172.28.0.20 │       │
│  └─────────────┘      └─────────────┘       │
└─────────────────────────────────────────────┘
```

### Port Mapping Strategy

| Internal | External | Configurable | Service |
|----------|----------|--------------|---------|
| 5900 | `${VNC_PORT}` | Yes | VNC |
| 6080 | `${WEB_VNC_PORT}` | Yes | Web VNC |
| 29999 | `${DASHBOARD_PORT}` | Yes | Dashboard |
| 30001-30004 | Same | Yes | Robot I/F |

---

## Build System

### Multi-Stage Dockerfile

```
┌─────────────────────────────────────────────┐
│                 base stage                  │
│  • ROS2 ${ROS_DISTRO} desktop               │
│  • Common dependencies                      │
├─────────────────────────────────────────────┤
│                driver stage                 │
│  • UR packages from apt                     │
│  • Fallback: build from source              │
├─────────────────────────────────────────────┤
│              workspace stage                │
│  • Optional source build                    │
│  • Custom packages                          │
├─────────────────────────────────────────────┤
│               runtime stage                 │
│  • Non-root user                            │
│  • CycloneDDS                               │
│  • Entrypoint configuration                 │
└─────────────────────────────────────────────┘
```

### Build Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `ROS_DISTRO` | humble | Target ROS2 distribution |
| `BUILD_FROM_SOURCE` | false | Build driver from source |
| `URCAP_VERSION` | 1.0.5 | ExternalControl URCap version |

---

## Scripts Reference

### build.sh

```bash
# Build with default (humble)
./docker/scripts/build.sh

# Build for specific distro
./docker/scripts/build.sh jazzy
```

### start.sh

```bash
# Simulation mode
./docker/scripts/start.sh sim

# Real robot
./docker/scripts/start.sh real --robot-ip 192.168.1.100

# With options
./docker/scripts/start.sh sim \
  --ros-distro jazzy \
  --robot-model UR10 \
  --detach
```

### stop.sh

```bash
# Stop all services
./docker/scripts/stop.sh
```

### status.sh

```bash
# Check stack status
./docker/scripts/status.sh
```

---

## Real Robot Integration

### Network Setup

```
┌──────────────────────────────────────────────────────────────┐
│                         Your Network                         │
│                                                              │
│  ┌─────────────────┐              ┌─────────────────┐        │
│  │   Your PC       │              │   Real Robot    │        │
│  │  192.168.1.50   │◄────────────►│  192.168.1.100  │        │
│  │                 │   Ethernet   │                 │        │
│  │  ┌───────────┐  │              │                 │        │
│  │  │  Docker   │  │              │                 │        │
│  │  │ ur-driver │  │              │                 │        │
│  │  └───────────┘  │              │                 │        │
│  └─────────────────┘              └─────────────────┘        │
└──────────────────────────────────────────────────────────────┘
```

### Configuration Steps

1. **Set robot IP in .env:**
   ```bash
   ROBOT_IP=192.168.1.100
   UR_TYPE=ur5e
   ```

2. **Extract calibration (recommended):**
   ```bash
   docker compose run --rm ur-driver bash -c "
     ros2 launch ur_calibration calibration_correction.launch.py \
       robot_ip:=192.168.1.100 \
       target_filename:=/calibration/robot_calibration.yaml
   "
   ```

3. **Start driver:**
   ```bash
   docker compose --profile real up
   ```

4. **On robot teach pendant:**
   - Configure ExternalControl URCap with Docker host IP
   - Run ExternalControl program

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Image build fails | Check internet connection, try `--no-cache` |
| URSim not starting | Check port conflicts, increase memory |
| Driver can't connect | Verify network, check firewall |
| No GUI display | Run `xhost +local:docker` |
| DDS discovery issues | Use same `ROS_DOMAIN_ID` |

### Debug Commands

```bash
# View logs
docker compose logs -f ur-driver

# Shell into container
docker compose exec ur-driver bash

# Check network
docker network inspect robots_ur-network

# Test connectivity
docker compose exec ur-driver nc -zv 172.28.0.10 30001
```

---

## Extending the Architecture

### Adding Custom ROS2 Packages

1. Create workspace directory:
   ```bash
   mkdir -p workspace/src
   ```

2. Add your packages to `workspace/src/`

3. Build in dev container:
   ```bash
   docker compose --profile dev run --rm ros2-dev bash -c "
     cd /home/ros/workspace &&
     colcon build
   "
   ```

### Adding New Services

Add to `docker-compose.yml`:

```yaml
services:
  my-custom-node:
    image: ur-ros2-driver:${ROS_DISTRO}
    networks:
      - ur-network
    command: ros2 run my_package my_node
```

---

## Version Compatibility Matrix

| ROS2 Distro | ur_robot_driver | URSim | Ubuntu |
|-------------|-----------------|-------|--------|
| Humble | 2.x | 5.x | 22.04 |
| Iron | 2.x | 5.x | 22.04 |
| Jazzy | 2.x | 5.x | 24.04 |
| Rolling | main | 5.x | 24.04 |

---

*Document Version: 1.0*
*Last Updated: January 2026*
