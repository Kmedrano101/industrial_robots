# Network Architecture

Wire layout, IP addressing, and every TCP port involved in talking to a
PolyScope 5 Universal Robots arm from this stack.

> Authoritative reference: UR's
> [Network setup](https://docs.universal-robots.com/Universal_Robots_ROS2_Documentation/doc/ur_client_library/doc/setup/network_setup.html)
> and [Robot setup](https://docs.universal-robots.com/Universal_Robots_ROS2_Documentation/doc/ur_client_library/doc/setup/robot_setup.html)
> docs. This page reflects how we apply them on top of the
> `ur-printer` / `web-ui` two-container stack.

---

## Wire layout

A typical deployment:

```
                       ┌──────────────────────────┐
                       │      Host PC (Linux)     │
                       │                          │
                       │  Browser                 │
                       │     │ http               │
                       │     ▼                    │
                       │  ┌────────────────┐      │
                       │  │  ur-web-ui     │      │
                       │  │  :8090         │      │
                       │  └───┬────────────┘      │
                       │      │ DDS               │
                       │      ▼                   │
                       │  ┌────────────────┐      │
                       │  │  ur-printer    │      │
                       │  │  ur_robot_driver│     │
                       │  │  RTDE client   │      │
                       │  └───┬────────────┘      │
                       │      │ TCP 30001-30004   │
                       │      │ + reverse :50001  │
                       │   eth0                   │
                       └──────│───────────────────┘
                              │   200.200.2.1/24
                  direct ethernet cable (no switch)
                              │   200.200.2.2/24
                       ┌──────│─────────────┐
                       │   eth (UR control) │
                       │                    │
                       │    UR Control Box  │
                       │    PolyScope 5     │
                       │  ExternalControl   │
                       │  URCap (.jar)      │
                       └────────────────────┘
```

**Why direct cable (no switch)**: UR's docs note that a switch in the
middle introduces variable latency that can violate the 8 ms RTDE cycle.
A managed switch with QoS is fine; an unmanaged hub is not. When in
doubt, plug them point-to-point.

---

## IP addressing

The repo defaults to a `/24` on `200.200.2.0`. You can pick anything, but
both sides have to agree.

| Where | Variable | Default | What it is |
|---|---|---|---|
| `.env` | `DRIVER_IP` | `200.200.2.1` | Host PC IP. The robot dials this back when ExternalControl runs. |
| `.env` | `ROBOT_IP` | `200.200.2.2` | UR arm IP. The driver dials this for RTDE / dashboard. |
| Pendant Installation → External Control | "Host IP" | must equal `DRIVER_IP` | tells the URCap where to phone home |

### Set IP on the host

NetworkManager:

```bash
nmcli connection add type ethernet con-name ur-cable ifname enp3s0 \
    ipv4.method manual ipv4.addresses 200.200.2.1/24
nmcli connection up ur-cable
```

…or `netplan`, `systemd-networkd`, etc. Pick whichever matches your
distro.

### Set IP on the robot

PolyScope 5 → **Settings → System → Network** — see UR's
[Network setup](https://docs.universal-robots.com/Universal_Robots_ROS2_Documentation/doc/ur_client_library/doc/setup/network_setup.html)
for the pendant screenshots:

| Field | Value |
|---|---|
| Network method | Static |
| IP address | `200.200.2.2` |
| Subnet mask | `255.255.255.0` |
| Default gateway | leave blank (point-to-point) |
| DNS | leave blank |

Apply, then verify from the host:

```bash
ping -c3 200.200.2.2     # should answer
```

---

## TCP ports

### Outbound (driver → robot)

Opened by `ur-printer` against the robot:

| Port | Protocol | Used by |
|---|---|---|
| `30001` | Primary client | Dashboard health / robot mode polling |
| `30002` | Secondary client | URScript program upload (the ExternalControl bootstrap script) |
| `30003` | Real-time client | Legacy real-time data stream |
| `30004` | RTDE | Joint states, force/torque, IO, servo command stream (8 ms cycle by default) |
| `29999` | Dashboard | `load`, `play`, `stop`, `robotmode` — used by `robot_state_helper` |

### Inbound (robot → driver)

Opened by `ur-printer` for the URCap to connect back:

| Port | Protocol | Used by |
|---|---|---|
| `50001` (default `reverse_port`) | TCP | ExternalControl URCap → driver. Carries trajectory chunks at 500 Hz. |
| `50002` (default `script_sender_port`) | TCP | Driver pushes the per-print URScript program to the URCap. |
| `50003` (default `trajectory_port`) | TCP | Acknowledgement channel for joint trajectory streams. |
| `50004` (default `script_command_port`) | TCP | Live URScript commands (freedrive, force mode toggles). |

All four are configurable in `ur_control.launch.py` if they collide with
something already running on the host.

### Host-facing (you → browser)

| Port | Service |
|---|---|
| `8090` | FastAPI backend + static React frontend (`ur-web-ui`) |
| `8090/api/ws` | WebSocket — joint_states, print state, extruder state, progress |

---

## DDS between containers

Both containers run with `network_mode: host`, so DDS discovery (multicast
`239.255.0.x`) works over the loopback `lo` interface automatically.

The DDS implementation is **CycloneDDS** (set via `RMW_IMPLEMENTATION` in
`.env`). The profile lives at `./config/cyclonedds.xml` and is mounted
read-only into both containers at `/config/cyclonedds.xml`.

Topics that cross the container boundary:

- `/joint_states` — driver → web-ui (live joint values)
- `/print_state`, `/print_progress`, `/extruder_state` — print_node → web-ui
- `/start_print`, `/pause_print`, `/cancel_print` — web-ui → print_node (service calls)

`ROS_DOMAIN_ID` must be identical on both containers (default `10`).

---

## Reverse-channel flow (the part that confuses people)

When the operator presses Play on the pendant with an ExternalControl
program loaded, the URCap on the robot does this:

1. Read the configured **Host IP** (= `DRIVER_IP`).
2. Open a TCP socket to `DRIVER_IP:50002` (`script_sender_port`).
3. Driver sends back a URScript template — pre-built with the
   `reverse_port`, `trajectory_port`, `script_command_port`.
4. URCap interprets the URScript and opens **three** sockets back to the
   driver: `:50001` (reverse), `:50003` (trajectory), `:50004` (commands).
5. From this point, **the robot drives the connection** — every 2 ms it
   sends joint states over `:30004` and accepts servoj waypoints over
   `:50001`.

If you don't see these connections established within ~10 s of pressing
Play, look at:

- The pendant log (Log → Controller log) for socket errors.
- `docker logs ur-printer` for `Connection to reverse interface dropped`.

The most common causes:
- Host IP in the URCap doesn't match `DRIVER_IP`.
- Firewall on the host blocking inbound `:50001-:50004` (allow them, or
  disable `ufw` on the trusted NIC).
- Robot is in **Local** control mode, not Remote. Set Remote in Settings
  → System → Remote Control.

---

## Optional: PREEMPT_RT kernel

The driver runs the RTDE loop at 500 Hz. With a stock kernel the average
case is fine but worst-case latency spikes can corrupt the 2 ms cycle.
UR's official recommendation is `PREEMPT_RT`:

```bash
uname -v | grep -i rt    # confirm you're on an RT kernel
```

If not, see UR's
[real-time setup guide](https://docs.universal-robots.com/Universal_Robots_ROS2_Documentation/doc/ur_client_library/doc/real_time.html).
The container is already configured with `SYS_NICE`, `IPC_LOCK`,
`rtprio: 99` and `memlock: -1` — it just needs a kernel that honours
SCHED_FIFO without forcing rt-throttling.

Quick sanity check from the host:

```bash
# /proc/sys/kernel/sched_rt_runtime_us should be -1 (no throttling)
cat /proc/sys/kernel/sched_rt_runtime_us
```

To remove throttling permanently:

```bash
echo 'kernel.sched_rt_runtime_us=-1' | sudo tee /etc/sysctl.d/99-rt.conf
sudo sysctl --system
```

---

## Diagnostics cheat sheet

```bash
# Is the robot reachable?
ping -c3 $ROBOT_IP

# RTDE port reachable?
nc -vz $ROBOT_IP 30004

# Dashboard reachable?
echo robotmode | nc -w 2 $ROBOT_IP 29999

# Are the inbound URCap ports listening on the host?
ss -tlnp | grep -E '5000[1-4]'

# Driver retry-looping?
docker logs ur-printer 2>&1 | grep "Failed to connect"

# DDS topics visible from web-ui?
docker exec ur-web-ui bash -c \
    "source /opt/ros/${ROS_DISTRO:-jazzy}/setup.bash && ros2 topic list"

# Joint states actually publishing?
docker exec ur-printer bash -c \
    "source /opt/ros/${ROS_DISTRO:-jazzy}/setup.bash && \
     source /ros2_ws/install/setup.bash && \
     ros2 topic hz /joint_states"
```
