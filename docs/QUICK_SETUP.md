# Quick Setup

End-to-end first-time setup for the UR 3D Printer stack. From a clean
checkout to a sliced toolpath rendering in the browser takes ~10 minutes
on a typical laptop (most of it spent in `docker compose build`).

> The instructions below assume **PolyScope 5**. The PolyScope X URCapX
> path is not supported on this branch.

---

## 1. Prerequisites

| Tool | Version | How to check |
|---|---|---|
| Docker Engine | 24.0+ | `docker --version` |
| Docker Compose plugin | v2.20+ | `docker compose version` |
| Git | any recent | `git --version` |

You do **not** need ROS2 installed on the host. Everything ROS lives inside
`ur-printer`.

Optional but recommended for production prints: a `PREEMPT_RT` or
`lowlatency` kernel. Stock Ubuntu kernels work for development.

Disk: ~6 GB for the two images plus dependencies.

---

## 2. Clone & configure

```bash
git clone <repo-url> industrial_robots
cd industrial_robots
cp .env.example .env
```

Edit `.env` with the values for your robot. The defaults are oriented at a
direct-Ethernet setup with the robot on `200.200.2.2/24` and the host on
`200.200.2.1/24`:

```env
# Robot
UR_TYPE=ur5e            # ur3e | ur5e | ur7e | ur10e | ur12e | ur16e | ur20 | ur30
ROBOT_IP=200.200.2.2    # the IP you assigned on the pendant
DRIVER_IP=200.200.2.1   # this host's IP (matches ExternalControl URCap "Host IP")
HEADLESS_MODE=true      # driver does not wait for the teach pendant
EXTRUDER_TYPE=fdm       # fdm | paste

# ROS2
ROS_DISTRO=jazzy
ROS_DOMAIN_ID=10        # any value 0-232; both containers must match
RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# Image tag (used by docker-compose)
IMAGE_TAG=ur-3d-printer:jazzy

# Web UI
WEB_UI_PORT=8090
```

If you don't have a robot yet, leave `ROBOT_IP` at the default — the
driver will spin in a retry loop but the rest of the stack works.

---

## 3. Build the images

```bash
docker compose build
```

First build: ~5–10 min. Subsequent builds are incremental.

What this does:

- Builds `ur-3d-printer:jazzy` (ROS2 base + `ur_robot_driver` + colcon
  build of the workspace).
- Builds `ur-3d-printer-web:latest` (multi-stage: Vite frontend + FastAPI
  backend with `rclpy`).

---

## 4. Start the stack

```bash
docker compose up -d
docker compose ps
```

Expected:

```
NAME         IMAGE                      STATUS
ur-printer   ur-3d-printer:jazzy        Up (health: starting)
ur-web-ui    ur-3d-printer-web:latest   Up
```

Tail the driver logs to see it boot:

```bash
docker compose logs -f ur-printer
```

You will see:

```
[ur-printer] no calibration at /calibration/ur5e_calibration.yaml — using nominal kinematics …
[INFO] [launch.user]: ============================================================
[INFO] [print_node]: Print node initialized for ur5e
[ERROR] [UR_Client_Library]: Failed to connect to robot on IP 200.200.2.2:30001. Retrying in 10 seconds.
```

The retry-loop is **expected** without a robot. The `print_node`,
`kinematics_server`, `extruder_controller` and visualizers are all up.

---

## 5. Open the web UI

Open <http://localhost:8090> in any modern browser. You should see the
**Robot 3D Printer** UI with:

- Header bar with state indicator (will say `Ready`)
- An empty 3D viewport with the print bed
- A right-side panel: `Prepare` (default) and `Live` tabs

Health check from the terminal:

```bash
curl -fsS http://localhost:8090/api/health
# {"status":"ok","ros2_connected":false,"websocket_clients":0}
```

`ros2_connected` flips to `true` when `/joint_states` is being published.

---

## 6. Slice and preview an STL (no robot needed)

1. Click the **dropzone** or drag-and-drop an `.stl` file.
2. The model preview appears centered on the bed.
3. In **Slice Settings** pick:
   - **Slicer Mode** — `Planar` (basic) or `Multi-axis` (tilts the nozzle
     to follow surface normals).
   - **Infill Pattern** — `Linear` / `Unidirectional` / `Reciprocating` /
     `Concentric Offset` / `Z-shaped` / `Planar Spiral` / `None`.
   - **Infill Density** — slider, 5 – 100%.
   - Layer height, print speed, scale.
4. Hit **Slice**. The toolpath renders in the viewport — drag the layer
   slider to walk through the print.

The slice runs server-side in the FastAPI backend; no ROS / robot is
required for this step.

---

## 7. Connect a real robot (PolyScope 5)

Three one-time operator steps. The two sources of truth on the robot
side are UR's official
[Robot setup](https://docs.universal-robots.com/Universal_Robots_ROS2_Documentation/doc/ur_client_library/doc/setup/robot_setup.html)
and
[Network setup](https://docs.universal-robots.com/Universal_Robots_ROS2_Documentation/doc/ur_client_library/doc/setup/network_setup.html)
docs — refer to them for the exact pendant screens. The summary below
is the minimum to get this stack talking to the arm.

### 7.1 Network

| Side | IP | Where to set |
|---|---|---|
| Host PC NIC | `200.200.2.1/24` | OS network manager |
| UR arm | `200.200.2.2/24` | Pendant → Settings → System → Network |

Verify with `ping 200.200.2.2` from the host. Detailed pendant flow:
[UR Network setup](https://docs.universal-robots.com/Universal_Robots_ROS2_Documentation/doc/ur_client_library/doc/setup/network_setup.html).

### 7.2 Install the ExternalControl URCap

1. Download `externalcontrol-1.0.5.urcap` from the
   [URCap releases](https://github.com/UniversalRobots/Universal_Robots_ExternalControl_URCap/releases).
2. Copy it to the robot (USB stick or `scp /programs/`).
3. Pendant → **Settings → System → URCaps → +** → pick the file.
4. Reboot the robot when prompted.
5. **Installation tab → External Control → Host IP** = `200.200.2.1`
   (your `DRIVER_IP`). Leave Custom Port at default.

![URSim External Control configuration](images/ursim-external-control.png)

6. Create or open a program, add an **External Control** node, save.

![URSim program with External Control node](images/ursim-program.png)

7. **Settings → System → Remote Control** — enable Remote Control mode.

### 7.3 Extract kinematics calibration

With the robot powered on (idle is fine):

```bash
docker exec -it ur-printer /usr/local/bin/extract_calibration.sh
docker compose restart ur-printer
```

Output: `./config/calibration/${UR_TYPE}_calibration.yaml` (persisted
on the host via volume). The driver auto-loads it on subsequent starts.

### 7.4 Run a print

In the pendant, press **Play** on your External Control program. The
driver will log:

```
Robot connected to reverse interface. Ready to receive control commands.
```

`ur-printer` health flips to `healthy`. In the browser, upload an STL,
slice, and click **Start Print**.

---

## 8. URSim simulator (optional, no real robot)

If you don't have a robot, you can validate the full pipeline against
UR's official simulator. URSim is **not** included in this branch's
compose file because the typical workflow on this branch targets the
real arm. To add it:

```bash
docker run --rm -d --name ursim \
  -p 5900:5900 -p 6080:6080 -p 29999:29999 \
  -p 30001:30001 -p 30002:30002 -p 30003:30003 -p 30004:30004 \
  --hostname ursim \
  -v $PWD/programs:/ursim/programs \
  -v ursim-urcaps:/urcaps \
  universalrobots/ursim_e-series
```

Then point `.env`:

```env
ROBOT_IP=127.0.0.1
DRIVER_IP=127.0.0.1
```

Open <http://localhost:6080/vnc.html> to access the simulated pendant,
install the URCap (Step 7.2), and press Play.

> Note: URSim binds the same RTDE ports as a real robot, so you can't run
> both at the same time.

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `docker compose build ur-printer` fails on `pip3 install` with PEP 668 | Old Dockerfile cached | `docker compose build --no-cache ur-printer` |
| `ur-printer` keeps logging `Failed to connect to robot on IP …` | Robot off / wrong IP / cable / firewall | Verify `ping ROBOT_IP`, robot booted, NIC IP matches `DRIVER_IP` |
| `ur-printer` health stays `unhealthy` after Play | URCap host IP wrong; remote control disabled; calibration mismatch | Check pendant: Installation → External Control host IP; enable Remote Control; check driver log for calibration warning |
| Browser shows `Slice failed: STL file not found` | Container was recreated; old localStorage points to a deleted path | Re-upload (the frontend clears the stale path on the next attempt) |
| Browser turns black after Slice on a complex STL | WebGL context lost from too many meshes | This was fixed by the v1.0 viewer rewrite; if you still see it, lower density or check GPU drivers |
| `rclpy not available` in `ur-web-ui` logs | DDS RMW mismatch between containers | Ensure both containers see the same `RMW_IMPLEMENTATION` and `ROS_DOMAIN_ID` |

Driver-side troubleshooting (real robot specific) lives in
[`workspace/ur_3d_printer/README.md`](../workspace/ur_3d_printer/README.md#troubleshooting).

---

## Next steps

- Read the [Docker architecture](DOCKER_ARCHITECTURE.md) for what each
  service does and how to extend the compose.
- Read the [Network architecture](NETWORK_ARCHITECTURE.md) for the wire
  layout and every TCP port involved.
- Read the [package README](../workspace/ur_3d_printer/README.md) for
  launch modes, ROS topics/services and the print state machine.
