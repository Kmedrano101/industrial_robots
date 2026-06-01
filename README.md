<div align="center">

# UR 3D Printer

### Turn any Universal Robots arm into a 3D printer

[![ROS2 Jazzy](https://img.shields.io/badge/ROS2-Jazzy-blue?style=for-the-badge&logo=ros)](https://docs.ros.org/en/jazzy/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-Apache%202.0-green?style=for-the-badge)](LICENSE)
[![Universal Robots](https://img.shields.io/badge/PolyScope%205-supported-red?style=for-the-badge)](https://www.universal-robots.com/)

<p align="center">
  <strong>STL → toolpath → robot motion, in a two-container stack you can run on a laptop.</strong>
</p>

![UR 3D Printer overview](docs/images/printer_overview.png)

[Quick Launch](#quick-launch) ·
[Architecture](#architecture) ·
[Bring up a real robot](#real-robot-bring-up-polyscope-5) ·
[Documentation](#documentation)

</div>

---

## What this is

A ROS2 package + web interface that converts a Universal Robots arm (UR3e–UR30) into an FDM-style 3D printer:

- **G-code parser** + planar/multi-axis slicer (six infill patterns: linear, unidirectional, reciprocating, concentric offset, Z-shaped, planar spiral).
- **Screw-theory kinematics** (Product of Exponentials) — single C++17 library with Python bindings, works for every UR model.
- **Trajectory streaming** to the official `ur_robot_driver` via `JointTrajectory`, fed by a print state machine.
- **Browser UI** at `http://localhost:8090` — upload STL, choose pattern + density, watch the toolpath render in 3D (Three.js / React Three Fiber), start/pause/cancel the print.
- **Two containers**: `ur-printer` (ROS2 + driver + app nodes) and `ur-web-ui` (FastAPI + static frontend). No host ROS install needed.

> The arm needs to be PolyScope 5 (the `.jar` URCap). PolyScope X is **not** supported on this branch.

---

## Quick Launch

Prerequisites: Docker + Docker Compose, ~6 GB disk for the images. **No host ROS install required.**

```bash
# 1. Clone and enter
git clone <repo-url> industrial_robots && cd industrial_robots

# 2. Copy and edit env file (set ROBOT_IP, UR_TYPE for your arm)
cp .env.example .env
$EDITOR .env

# 3. Build both images (~5-10 min first time)
docker compose build

# 4. Bring up the stack
docker compose up -d

# 5. Open the web UI
xdg-open http://localhost:8090     # or just open it in your browser
```

What you should see:

| Container | Status | Notes |
|---|---|---|
| `ur-printer` | `Up — health: starting` → `healthy` once `/joint_states` is published | retry-loop logged until a robot is reachable at `ROBOT_IP` — expected |
| `ur-web-ui` | `Up` | health endpoint at `/api/health` |

To see logs as they happen:

```bash
docker compose logs -f ur-printer
```

Without a robot connected the driver will retry the RTDE connection every 10 s. That's normal — the web UI is fully functional for slicing and visualization on its own.

---

## Architecture

Two services, host networking, shared CycloneDDS config:

```
┌────────────────────────────────────────────────────────────────┐
│ Host PC (Linux, optionally PREEMPT_RT kernel)                  │
│                                                                │
│   ┌──────────────────────┐     ┌────────────────────────────┐  │
│   │  ur-printer          │     │  ur-web-ui                 │  │
│   │  ─────────────       │     │  ─────────                 │  │
│   │  ros2 launch         │     │  FastAPI + React build     │  │
│   │   - ur_robot_driver  │     │   - REST /api/* ──────┐    │  │
│   │   - kinematics_node  │◄──DDS──── joint_states      │    │  │
│   │   - extruder_ctrl    │     │   - WebSocket /api/ws │    │  │
│   │   - print_node       │     │   - STL upload / slice│    │  │
│   │   - visualizers      │     │     ↑                 │    │  │
│   │                      │     │     └─ Browser :8090  │    │  │
│   │  rtprio:99           │     └────────────────────────────┘  │
│   │  network_mode: host  │                                     │
│   └─────────┬────────────┘                                     │
└─────────────┼──────────────────────────────────────────────────┘
              │ RTDE / Primary / Secondary / RT
              │ (TCP 30001-30004)
              ▼
        ┌──────────────┐
        │ UR arm (PS5) │
        │ ExternalCtrl │
        │ URCap (.jar) │
        └──────────────┘
```

Details:

- **`ur-printer`** — `ros:jazzy-ros-base` base with `ur-robot-driver`, `ur-description`, `ur-calibration` apt packages and the colcon-built `ur_3d_printer` workspace. Runs `print_driver.launch.py` with `headless_mode:=true`.
- **`ur-web-ui`** — multi-stage Dockerfile: stage 1 builds the Vite/React frontend, stage 2 ships a FastAPI backend with `rclpy`. Backend subscribes to ROS topics through DDS and pushes them to the browser via WebSocket.
- **Real-time** — `cap_add: [SYS_NICE, IPC_LOCK]`, `ulimits.rtprio: 99`, `ulimits.memlock: -1`. Pair with a `PREEMPT_RT` or `lowlatency` kernel on the host for production prints.

See [docs/DOCKER_ARCHITECTURE.md](docs/DOCKER_ARCHITECTURE.md) for the full breakdown.

---

## Real Robot Bring-up (PolyScope 5)

Connecting a physical UR arm requires three one-time operator steps. After that, container restarts just work.

### 1. Network

Direct Ethernet between the host and the robot (no switches recommended). Defaults expect:

| Side | IP | Notes |
|---|---|---|
| Host PC | `200.200.2.1/24` (or whatever you configure) | matches `DRIVER_IP` in `.env` |
| UR arm | `200.200.2.2/24` (or whatever you configure) | matches `ROBOT_IP` in `.env` |

Set both via the robot teach pendant (Settings → System → Network) and your host NIC. Verify with `ping`.

Full network setup including PolyScope screens: [docs/NETWORK_ARCHITECTURE.md](docs/NETWORK_ARCHITECTURE.md). Official UR reference: [Network setup](https://docs.universal-robots.com/Universal_Robots_ROS2_Documentation/doc/ur_client_library/doc/setup/network_setup.html).

### 2. Install the ExternalControl URCap

Download `externalcontrol-1.0.5.urcap` from the [URCap releases](https://github.com/UniversalRobots/Universal_Robots_ExternalControl_URCap/releases) and install it on the pendant (Settings → System → URCaps → +). Reboot the robot, then configure the **Host IP** to your `DRIVER_IP`.

Step-by-step: see [`workspace/ur_3d_printer/README.md`](workspace/ur_3d_printer/README.md#real-robot-bring-up-polyscope-5). Official UR reference: [Robot setup](https://docs.universal-robots.com/Universal_Robots_ROS2_Documentation/doc/ur_client_library/doc/setup/robot_setup.html).

### 3. Extract kinematics calibration

The nominal kinematics in `ur_description` are accurate to within centimetres of the arm-class average — fine for visualisation, not for printing. Extract your arm's specific calibration:

```bash
docker compose up -d ur-printer
docker exec -it ur-printer /usr/local/bin/extract_calibration.sh
docker compose restart ur-printer
```

Output lands at `./config/calibration/${UR_TYPE}_calibration.yaml` on the host (persisted via volume mount) and is auto-loaded on subsequent driver starts.

---

## Documentation

| Doc | Covers |
|---|---|
| [`docs/QUICK_SETUP.md`](docs/QUICK_SETUP.md) | Step-by-step first-time setup, including URSim simulator option |
| [`docs/DOCKER_ARCHITECTURE.md`](docs/DOCKER_ARCHITECTURE.md) | Why two containers, what each does, volumes, capabilities, healthcheck |
| [`docs/NETWORK_ARCHITECTURE.md`](docs/NETWORK_ARCHITECTURE.md) | Host networking, RTDE ports, ExternalControl reverse channel, PolyScope 5 setup |
| [`workspace/ur_3d_printer/README.md`](workspace/ur_3d_printer/README.md) | The ROS2 package: launch modes, nodes, topics, services, calibration extraction, troubleshooting |
| [`workspace/ur_3d_printer/docs/`](workspace/ur_3d_printer/docs/) | Per-module architecture (modules, pipeline, interfaces, configuration) |

---

## Repository layout

```
.
├── docker/
│   └── ros2-printer/        ← ur-printer image (ROS2 + UR driver + workspace)
│       ├── Dockerfile
│       ├── entrypoint.sh
│       └── extract_calibration.sh
├── docs/                    ← this directory
├── config/
│   ├── cyclonedds.xml       ← DDS profile mounted into both containers
│   └── calibration/         ← extract_calibration.sh writes YAML here
├── workspace/               ← ROS2 source
│   ├── ur_3d_printer/       ← the application package
│   ├── ur_3d_printer_web/   ← FastAPI backend + Vite/React frontend
│   ├── ur_kinematics_msgs/  ← custom msg/srv
│   ├── ur_kinematics_node/  ← Python ROS node wrapping the C++ kinematics
│   └── ur_screw_kinematics/ ← C++17 screw-theory FK/IK library
├── docker-compose.yml
├── .env.example
└── README.md                ← you are here
```

---

## License

Apache-2.0 — see [LICENSE](LICENSE).

---

## Contributing

Issues and PRs welcome. Please follow the commit message convention:
`<type>: <description>` where `<type>` is one of `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.
