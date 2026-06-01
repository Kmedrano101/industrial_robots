#!/usr/bin/env bash
# =============================================================================
# Extract kinematics calibration from a real UR robot.
#
# Per UR docs (https://docs.universal-robots.com/Universal_Robots_ROS2_Documentation/
# doc/ur_robot_driver/ur_robot_driver/doc/installation/robot_setup.html), the
# nominal kinematics shipped with ur_description are off by centimetres on
# specific units. The official `ur_calibration` package contacts the robot
# (which must be **powered on, idle is fine**) and writes a YAML the driver
# loads at runtime.
#
# Usage (host):
#   docker compose up -d ur-printer            # container must already be up
#   docker exec -it ur-printer /workspace/extract_calibration.sh
#
# Or directly:
#   ROBOT_IP=200.200.2.2 UR_TYPE=ur5e ./extract_calibration.sh
#
# Output:
#   /calibration/${UR_TYPE}_calibration.yaml   (mounted from host
#   ./config/calibration/${UR_TYPE}_calibration.yaml). Subsequent driver
#   restarts pick it up automatically via KINEMATICS_PARAMS_FILE.
# =============================================================================

set -euo pipefail

ROBOT_IP="${ROBOT_IP:-${1:-}}"
UR_TYPE="${UR_TYPE:-${2:-ur5e}}"
OUT_DIR="${OUT_DIR:-/calibration}"
OUT_FILE="${OUT_DIR}/${UR_TYPE}_calibration.yaml"

if [ -z "$ROBOT_IP" ]; then
    echo "ERROR: ROBOT_IP not set." >&2
    echo "Usage: $0 <robot_ip> [ur_type]" >&2
    exit 2
fi

if [ ! -d "$OUT_DIR" ]; then
    echo "ERROR: $OUT_DIR does not exist (is the calibration volume mounted?)" >&2
    exit 3
fi

# Source ROS2 + workspace overlay. The container's entrypoint normally does
# this; sourcing again is idempotent when running via `docker exec`.
# shellcheck disable=SC1090
source "/opt/ros/${ROS_DISTRO}/setup.bash"
# shellcheck disable=SC1091
[ -f /ros2_ws/install/setup.bash ] && source /ros2_ws/install/setup.bash

echo "[extract_calibration] robot_ip=${ROBOT_IP}  ur_type=${UR_TYPE}"
echo "[extract_calibration] writing to ${OUT_FILE}"
echo "[extract_calibration] Make sure the robot is POWERED ON (idle is fine)."

# Quick reachability check before launching anything heavy.
if ! ping -c 1 -W 2 "$ROBOT_IP" >/dev/null 2>&1; then
    echo "WARN: cannot ping $ROBOT_IP — extraction will probably hang." >&2
fi

# ur_calibration writes the YAML and exits cleanly. We capture the exit code
# so failures (e.g. robot unreachable) surface clearly.
ros2 launch ur_calibration calibration_correction.launch.py \
    robot_ip:="${ROBOT_IP}" \
    target_filename:="${OUT_FILE}"

if [ -f "$OUT_FILE" ]; then
    echo
    echo "[extract_calibration] OK — wrote ${OUT_FILE}"
    echo "[extract_calibration] Restart the driver to pick it up:"
    echo "    docker compose restart ur-printer"
else
    echo "[extract_calibration] FAILED — output file not produced." >&2
    exit 4
fi
