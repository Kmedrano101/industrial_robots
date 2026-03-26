# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Containerized ROS2 framework for controlling Universal Robots arms (UR3e–UR30). Entirely Docker-based — no host ROS2 installation needed. Supports ROS2 Humble, Jazzy, and Rolling.

## Commit Messages

Format: `<type>: <description>`

| Type | Use for |
|------|---------|
| `feat:` | New features (user-visible functionality) |
| `fix:` | Bug fixes (resolving an issue/defect) |
| `docs:` | Documentation changes only (README, comments, guides) |
| `refactor:` | Code change that neither fixes a bug nor adds a feature |
| `style:` | Formatting, missing semi-colons, white space, etc (no code change) |
| `test:` | Adding or updating tests |
| `chore:` | Miscellaneous tasks (maintenance, package updates, tooling, etc.) |

## Build & Run Commands

### Docker Infrastructure

```bash
./docker/scripts/build.sh              # Build all Docker images
./docker/scripts/start.sh sim          # Start simulation (URSim + driver)
./docker/scripts/start.sh real --robot-ip <IP>  # Connect to physical robot
./docker/scripts/stop.sh               # Stop all services
./docker/scripts/status.sh             # Check service status
```

Docker Compose profiles: `sim`, `real`, `viz`, `dev`, `full`

### Building the ROS2 Workspace (inside container)

```bash
docker compose --profile dev up -d ros2-dev
docker exec -it ros2-dev bash
cd /home/ros/workspace
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

Build a single package: `colcon build --symlink-install --packages-select <package_name>`

### Running Tests

```bash
# All tests for a package
colcon test --packages-select ur_3d_printer
colcon test-result --verbose

# Single pytest file (after sourcing workspace)
python3 -m pytest workspace/src/ur_3d_printer/test/test_gcode_parser.py -v

# C++ tests (ur_screw_kinematics uses GTest)
colcon test --packages-select ur_screw_kinematics
```

### Launching Applications

```bash
# 3D printer standalone (no real robot)
ros2 launch ur_3d_printer print_standalone.launch.py gcode_file:=/tmp/model.gcode

# Pick and place
ros2 launch ur_pick_place pick_place.launch.py
```

## Architecture

### Package Dependency Graph

```
ur_kinematics_msgs  (ROS2 msg/srv definitions)
        ↓
ur_screw_kinematics (C++ kinematics library + pybind11 Python bindings)
        ↓
ur_kinematics_node  (ROS2 Python node exposing FK/IK as services)
        ↓
┌───────────────┬────────────────┐
│ ur_pick_place │ ur_3d_printer  │  (application packages)
└───────────────┴────────────────┘
```

### Key Packages (all under `workspace/src/`)

- **ur_screw_kinematics** — C++17 FK/IK solver using screw theory (Product of Exponentials). Uses Eigen3 for linear algebra, pybind11 for Python bindings. Config YAML files for each UR model under `config/`.
- **ur_kinematics_msgs** — Custom ROS2 message and service definitions for kinematics requests.
- **ur_kinematics_node** — Python ROS2 node wrapping the C++ kinematics library as ROS2 services.
- **ur_pick_place** — Pick-and-place demo with UR5e, parallel gripper, and worktable. Has URDF descriptions and launch files.
- **ur_3d_printer** — Most complex package. Converts UR arms into 3D printers. Modules: `gcode_parser.py` (G0/G1/G2/G3), `trajectory_planner.py` (IK + path planning), `velocity_profiler.py`, `collision_checker.py`, `multiaxis_planner.py`, `workspace_validator.py`, `toolpath.py` (data structures). Has 52+ unit tests across 6 test files.

### Docker Stack

Four main services on a custom bridge network (172.20.0.0/16):
1. **URSim** (172.20.0.2) — UR simulator with ExternalControl URCap, VNC on port 6080
2. **UR Driver** (172.20.0.3) — ROS2 UR driver with CycloneDDS, auto-loads ExternalControl program
3. **Web UI** (172.20.0.4) — React + FastAPI web interface for 3D printer control, port 8090
4. **RViz** (optional) — Visualization service

Configuration via `.env` file (copy from `.env.example`). Key variables: `ROS_DISTRO`, `UR_TYPE`, `ROBOT_IP`, `ROBOT_MODEL`, `WEB_UI_PORT`.

### Build System

- CMake + ament_cmake for C++ packages
- ament_python for Python packages
- colcon as the meta-build tool
- C++17 standard required
- pybind11 bridges C++ kinematics to Python

## Web Interface (`workspace/src/ur_3d_printer_web/`)

Production-ready web UI for the ur_3d_printer package. React frontend + FastAPI backend bridging to ROS2.

### Architecture

```
Browser → React (Vite + Tailwind + R3F) → FastAPI+rclpy backend → ROS2 topics/services
```

- **Frontend**: React + TypeScript + Vite, React Three Fiber for 3D, Zustand for state, Tailwind CSS, react-i18next (ES default/EN)
- **Backend**: FastAPI + rclpy single process. REST for commands, WebSocket for real-time data streaming
- **Slicing**: Server-side STL slicing via existing `stl_slicer.py` / `multiaxis_slicer.py`
- **Data flow**: STL upload → slice → toolpath preview with layer slider → start print → live progress via WebSocket

### Web Interface Commands

```bash
# Production (Docker)
docker compose build web-ui
docker compose --profile sim up               # Includes web UI at http://localhost:8080

# Frontend development (hot reload)
cd workspace/src/ur_3d_printer_web/frontend
npm install
npm run dev                                   # Vite dev server on :5173, proxies /api to :8080

# Backend development (inside ros2-dev container)
cd /home/ros/workspace/src/ur_3d_printer_web
pip install -r backend/requirements.txt
python3 -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8090

# Frontend tests
cd workspace/src/ur_3d_printer_web/frontend && npx vitest run

# Backend tests
cd workspace/src/ur_3d_printer_web/backend && python3 -m pytest
```

### Key Frontend Structure

- `stores/` — Zustand stores: `usePrintStore` (print state, progress, upload, slice), `useRobotStore` (joints), `useSettingsStore` (theme, lang)
- `hooks/useWebSocket.ts` — Auto-reconnecting WebSocket to `/api/ws`
- `components/viewer/` — 3D scene: `SceneCanvas`, `Toolpath`, `LayerSlider`, `StlPreview`, `PrintBed`
- `components/controls/` — `FileUpload`, `SliceSettings`, `PrintControlPanel`, `ExtruderPanel`
- `public/locales/{es,en}/` — i18n translation files

### Key Backend Endpoints

- `POST /api/upload` — STL file upload with validation
- `POST /api/slice` — Slice STL with configurable params → returns toolpath by layer
- `POST /api/print/{start,pause,resume,cancel}` — Print control → ROS2 services
- `WS /api/ws` — Real-time: print_state, print_progress, extruder_state, joint_states
