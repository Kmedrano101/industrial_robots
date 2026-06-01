# Docker Architecture

Two services, two Dockerfiles, one compose file. This page explains what
each container is, what it mounts, and why each capability/ulimit is set.

---

## Service map

```
┌────────────────────────────────────────────────────────────────────┐
│ docker-compose.yml                                                 │
│                                                                    │
│   ┌──────────────────────────┐    ┌──────────────────────────┐    │
│   │ ur-printer               │    │ web-ui (ur-web-ui)       │    │
│   │ ─────────────────        │    │ ─────────────────        │    │
│   │ image: ur-3d-printer:    │    │ image: ur-3d-printer-    │    │
│   │   jazzy                  │    │   web:latest             │    │
│   │ Dockerfile:              │    │ Dockerfile:              │    │
│   │   docker/ros2-printer/   │    │   workspace/             │    │
│   │   Dockerfile             │    │   ur_3d_printer_web/     │    │
│   │ base: ros:jazzy-ros-base │    │   docker/Dockerfile      │    │
│   │ network_mode: host       │    │ base: osrf/ros:jazzy-    │    │
│   │ cap_add: SYS_NICE,       │    │   desktop (multi-stage)  │    │
│   │   IPC_LOCK               │    │ network_mode: host       │    │
│   │ ulimits: rtprio 99,      │    │ port: 8090               │    │
│   │   memlock -1             │    │ depends_on: ur-printer   │    │
│   │ runs: ros2 launch        │    │ runs: uvicorn FastAPI    │    │
│   └──────────┬───────────────┘    └──────────┬───────────────┘    │
│              │ DDS (CycloneDDS)               │                    │
│              └────────── lo loopback ─────────┘                    │
└────────────────────────────────────────────────────────────────────┘
```

Both share `./config/cyclonedds.xml` (read-only mount) and the same
`ROS_DOMAIN_ID` so DDS discovery converges.

---

## `ur-printer`

The headless control-PC image. Runs the official UR driver plus this
project's ROS nodes.

### Image build

[`docker/ros2-printer/Dockerfile`](../docker/ros2-printer/Dockerfile):

1. `FROM ros:${ROS_DISTRO}-ros-base` (`jazzy` by default).
2. `apt install`:
   - `ros-${ROS_DISTRO}-ur-robot-driver`, `ur-description`,
     `ur-calibration`, `rmw-cyclonedds-cpp`, `xacro`,
     `robot-state-publisher`.
   - Build deps: `build-essential cmake git pybind11-dev libeigen3-dev`.
   - Toolchain: `python3-colcon-common-extensions python3-rosdep python3-vcstool`.
3. `pip3 install --break-system-packages numpy-stl trimesh scipy shapely`
   (Noble enforces PEP 668; needs explicit override for system Python).
4. `COPY workspace ./src` then `colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release`
   — colcon picks up `ur_3d_printer`, `ur_kinematics_node`, the C++
   `ur_screw_kinematics` library, and the custom `ur_kinematics_msgs`.
5. `COPY entrypoint.sh extract_calibration.sh` and a marker.

`rosdep install` is invoked with
`--skip-keys "rviz2 python3-shapely pybind11"`:

- `rviz2` — visualization is in the browser, not in this image.
- `python3-shapely` — apt package missing on Noble; installed via pip.
- `pybind11` — rosdep key not defined for jazzy; the binary `pybind11-dev`
  is already pulled by the apt list.

### Runtime config (from compose)

| Setting | Value | Why |
|---|---|---|
| `network_mode: host` | enabled | Direct path to robot on a separate NIC. NAT would break the URCap reverse channel. |
| `cap_add: SYS_NICE` | enabled | Required for `sched_setscheduler(SCHED_FIFO)` used by the RTDE loop. |
| `cap_add: IPC_LOCK` | enabled | Pairs with `memlock` so `mlockall()` doesn't `EPERM`. |
| `ulimits.rtprio` | 99 | UR client library can request RT priority. |
| `ulimits.memlock` | -1 | UR docs require ≥102400 KB; unlimited removes the ambiguity. |
| `restart: unless-stopped` | enabled | Driver should come back after host reboots / OOM events. |
| `healthcheck` | `ros2 topic list \| grep -q /joint_states` | Healthy iff the driver is publishing joint states (i.e. RTDE is up). |

### Environment passed in

```yaml
ROS_DOMAIN_ID:           ${ROS_DOMAIN_ID}
RMW_IMPLEMENTATION:      ${RMW_IMPLEMENTATION}   # rmw_cyclonedds_cpp
CYCLONEDDS_URI:          file:///config/cyclonedds.xml
UR_TYPE:                 ${UR_TYPE}              # e.g. ur5e
ROBOT_IP:                ${ROBOT_IP}             # e.g. 200.200.2.2
KINEMATICS_PARAMS_FILE:  /calibration/${UR_TYPE}_calibration.yaml
```

### Volumes

| Host | Container | Mode | Purpose |
|---|---|---|---|
| `./config/cyclonedds.xml` | `/config/cyclonedds.xml` | ro | DDS profile shared with `web-ui` |
| `./config/calibration/` | `/calibration/` | rw | Where `extract_calibration.sh` writes the YAML; persists across `docker compose down -v` |

### Launch command

The compose `command:` block (a bash heredoc) checks whether a
calibration file is present and only then appends the
`kinematics_params_file:=…` argument. The actual call expands to:

```bash
ros2 launch ur_3d_printer print_driver.launch.py \
    ur_type:=${UR_TYPE} \
    robot_ip:=${ROBOT_IP} \
    headless_mode:=true \
    extruder_type:=fdm \
    launch_rviz:=false \
    [kinematics_params_file:=/calibration/${UR_TYPE}_calibration.yaml]
```

`print_driver.launch.py` chains into `ur_control.launch.py` (official
driver) plus this package's `kinematics_server`, `extruder_controller`,
`toolpath_visualizer`, `deposition_visualizer`, and `print_node`.

### Helper scripts inside the image

| Path | What it does |
|---|---|
| `/entrypoint.sh` | Sources `/opt/ros/${ROS_DISTRO}/setup.bash` and `/ros2_ws/install/setup.bash`, then `exec "$@"`. |
| `/usr/local/bin/extract_calibration.sh` | One-shot helper. Runs `ur_calibration`'s correction launch against `ROBOT_IP` and drops `${UR_TYPE}_calibration.yaml` in `/calibration/`. Usage: `docker exec -it ur-printer /usr/local/bin/extract_calibration.sh`. |

---

## `web-ui`

The browser-facing interface. Single container that hosts both the
FastAPI backend and the pre-built React frontend as static files.

### Image build

[`workspace/ur_3d_printer_web/docker/Dockerfile`](../workspace/ur_3d_printer_web/docker/Dockerfile)
— multi-stage:

**Stage 1 (`frontend-build`, base `node:20-alpine`):**

```dockerfile
WORKDIR /app/frontend
COPY frontend/ ./
RUN npm ci && npm run build
# → /app/frontend/dist
```

**Stage 2 (`runtime`, base `osrf/ros:${ROS_DISTRO}-desktop`):**

1. `apt install python3-pip` + `ros-${ROS_DISTRO}-rmw-cyclonedds-cpp`.
2. Rename the base image's `ubuntu` UID-1000 user to `web` (the
   `osrf/ros:jazzy-desktop` image now ships with `ubuntu:1000` by
   default).
3. `pip3 install --break-system-packages -r requirements.txt`
   (FastAPI, uvicorn, pydantic, numpy, **shapely**, websockets).
4. `COPY backend/ /app/backend/` and the built static SPA from stage 1
   to `/app/static/`.
5. Sets `PYTHONPATH=/app:/app/web_package:/pkgs`.

### Runtime config

| Setting | Value | Why |
|---|---|---|
| `network_mode: host` | enabled | Lets backend's `rclpy` participate in the same DDS domain as `ur-printer` over `lo`. |
| `ports` | not exposed (host network already covers `:8090`) | Default `WEB_PORT=8090`. |
| `depends_on: ur-printer` | enabled | Compose start order only; the backend tolerates a missing ROS side at runtime (`ros2_connected: false`). |

### Volumes

| Host | Container | Mode | Purpose |
|---|---|---|---|
| `./config/cyclonedds.xml` | `/config/cyclonedds.xml` | ro | same DDS profile as `ur-printer` |
| `./workspace/ur_3d_printer` | `/pkgs/ur_3d_printer` | ro | exposes the ROS package's `resource/stl_slicer.py` + `multiaxis_planner.py` to the FastAPI backend so it can slice without rebuilding the image |

The second mount is the only reason the backend can find
`ur_3d_printer.resource.stl_slicer` and `ur_3d_printer.multiaxis_planner`
at runtime. A bridge in `slicer_service.py` extends the namespace
package's `__path__` so the outer dir (with `resource/`) and the inner
regular package (with `multiaxis_planner.py`) both resolve under the same
`ur_3d_printer` import.

### What it serves

| Route | Purpose |
|---|---|
| `GET /` | Static SPA shell (`/app/static/index.html`) |
| `GET /assets/*`, `/locales/*` | Vite bundle + i18n translations |
| `GET /api/health` | `{status, ros2_connected, websocket_clients}` |
| `POST /api/upload` | STL upload; saves under `/uploads/` |
| `POST /api/slice` | Server-side slicing using `stl_slicer.py` / `multiaxis_planner.py` |
| `POST /api/print/{start,pause,resume,cancel}` | Forwards to ROS services on `print_node` |
| `WS /api/ws` | Live: `print_state`, `print_progress`, `extruder_state`, `joint_states` |

---

## Shared `cyclonedds.xml`

[`./config/cyclonedds.xml`](../config/cyclonedds.xml) is mounted into both
containers and pointed at via `CYCLONEDDS_URI=file:///config/cyclonedds.xml`.
It typically pins multicast to the host loopback and selects a single
network interface so DDS discovery doesn't accidentally cross machine
boundaries.

If you change DDS implementations (e.g. switch to FastDDS), update
`RMW_IMPLEMENTATION` in `.env` and remove the `CYCLONEDDS_URI` env from
both services.

---

## Extending the stack

### Add URSim alongside the real-robot driver

URSim binds the same RTDE ports (`30001-30004`) as a real robot, so you
have to pick one or run them on separate hosts. To wire it in:

```yaml
ursim:
  image: universalrobots/ursim_e-series
  network_mode: host
  ports: ["5900:5900", "6080:6080"]
  volumes:
    - ./programs:/ursim/programs
    - ursim-urcaps:/urcaps
  profiles: [sim]
```

Then `ROBOT_IP=127.0.0.1` in `.env` and run
`docker compose --profile sim up`.

### Mount the ROS workspace for dev iteration

To edit Python in `ur_3d_printer/` without rebuilding `ur-printer`:

```yaml
ur-printer:
  volumes:
    - ./workspace/ur_3d_printer:/ros2_ws/src/ur_3d_printer
```

Note this only works because the package is colcon `ament_cmake_python`
with the resource marker — Python files are picked up by symlinking
during the install step. For C++ changes you still need a rebuild.

### Run multiple ROS_DOMAINs on one host

Bump `ROS_DOMAIN_ID` per stack (any value 0-232; both containers must
match within a stack). Each domain ID maps to a different multicast
group so several copies of the stack can coexist.

---

## Rebuilding

```bash
# Both
docker compose build

# One service
docker compose build ur-printer
docker compose build web-ui

# Force from scratch (e.g. after changing the Dockerfile chain)
docker compose build --no-cache ur-printer
```

After a rebuild, `up -d` automatically recreates running containers using
the new image.

---

## Lifecycle commands

```bash
docker compose up -d                 # start everything detached
docker compose ps                    # show status + health
docker compose logs -f ur-printer    # follow driver logs
docker compose restart ur-printer    # restart after calibration extraction
docker compose stop                  # stop without removing
docker compose down                  # stop + remove containers (volumes preserved)
docker compose down -v               # also wipe named volumes (uploads, urcaps)
```
