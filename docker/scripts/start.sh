#!/bin/bash
# =============================================================================
# Start UR + ROS2 Stack
# =============================================================================
# Usage: ./start.sh [mode] [options]
#
# Modes:
#   sim   - Start URSim + ROS2 Driver (default)
#   real  - Start ROS2 Driver for real robot
#   dev   - Start development container
#   full  - Start everything including RViz
#
# Options:
#   --robot-ip <ip>    - Robot IP (for real mode)
#   --ros-distro <d>   - ROS2 distro (humble, jazzy, rolling)
#   --robot-model <m>  - Robot model (UR3, UR5, UR10, etc.)
#   --detach           - Run in background
#
# Examples:
#   ./start.sh sim
#   ./start.sh real --robot-ip 192.168.1.100
#   ./start.sh sim --ros-distro jazzy --robot-model UR10
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Defaults
MODE=${1:-sim}
shift || true

DETACH=""
EXTRA_ARGS=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --robot-ip)
            export ROBOT_IP="$2"
            shift 2
            ;;
        --ros-distro)
            export ROS_DISTRO="$2"
            shift 2
            ;;
        --robot-model)
            export ROBOT_MODEL="$2"
            shift 2
            ;;
        --ur-type)
            export UR_TYPE="$2"
            shift 2
            ;;
        --detach|-d)
            DETACH="-d"
            shift
            ;;
        *)
            EXTRA_ARGS="$EXTRA_ARGS $1"
            shift
            ;;
    esac
done

cd "$PROJECT_DIR"

# Load .env if exists
if [ -f ".env" ]; then
    source .env
fi

echo "=============================================="
echo "  Starting UR + ROS2 Stack"
echo "=============================================="
echo "  Mode:        ${MODE}"
echo "  ROS Distro:  ${ROS_DISTRO:-humble}"
echo "  Robot Model: ${ROBOT_MODEL:-UR5}"
echo "  Robot IP:    ${ROBOT_IP:-172.28.0.10}"
echo "=============================================="

# Allow X11 forwarding for GUI
xhost +local:docker 2>/dev/null || true

case $MODE in
    sim)
        echo "Starting URSim + ROS2 Driver..."
        docker compose --profile sim up $DETACH $EXTRA_ARGS
        ;;
    real)
        if [ -z "$ROBOT_IP" ] || [ "$ROBOT_IP" = "172.28.0.10" ]; then
            echo "ERROR: Please specify robot IP with --robot-ip"
            exit 1
        fi
        echo "Starting ROS2 Driver for real robot at ${ROBOT_IP}..."
        docker compose --profile real up $DETACH $EXTRA_ARGS
        ;;
    dev)
        echo "Starting development container..."
        docker compose --profile dev run --rm ros2-dev
        ;;
    full)
        echo "Starting full stack with RViz..."
        docker compose --profile full up $DETACH $EXTRA_ARGS
        ;;
    *)
        echo "Unknown mode: $MODE"
        echo "Available modes: sim, real, dev, full"
        exit 1
        ;;
esac
