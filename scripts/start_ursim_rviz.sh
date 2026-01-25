#!/bin/bash
# =============================================================================
# Start URSim with ROS2 Driver and RViz Visualization (Native ROS2 version)
# =============================================================================
# This script:
#   1. Starts URSim (Universal Robots Simulator) in Docker
#   2. Launches ROS2 UR Robot Driver natively on the host
#   3. Optionally launches RViz visualization
#
# Prerequisites:
#   - Docker installed
#   - ROS2 with ur_robot_driver installed (apt or source)
#   - External Control URCap downloaded to ~/.ursim/urcaps/
#
# Usage: ./scripts/start_ursim_rviz.sh [--no-rviz] [--stop]
#
# Environment variables:
#   UR_TYPE      - Robot type (default: ur5e)
#   ROBOT_MODEL  - URSim model (default: UR5)
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration
UR_TYPE=${UR_TYPE:-ur5e}
ROBOT_MODEL=${ROBOT_MODEL:-UR5}
URSIM_CONTAINER="ursim"

# Parse arguments
LAUNCH_RVIZ=true
STOP_ONLY=false
for arg in "$@"; do
    case $arg in
        --no-rviz)
            LAUNCH_RVIZ=false
            ;;
        --stop)
            STOP_ONLY=true
            ;;
        --help|-h)
            echo "Usage: $0 [--no-rviz] [--stop]"
            echo ""
            echo "Options:"
            echo "  --no-rviz  Don't launch RViz"
            echo "  --stop     Stop URSim container and exit"
            exit 0
            ;;
    esac
done

# -----------------------------------------------------------------------------
# Stop mode
# -----------------------------------------------------------------------------
if [ "$STOP_ONLY" = true ]; then
    echo "Stopping URSim container..."
    docker rm -f "$URSIM_CONTAINER" 2>/dev/null || true
    echo "Done."
    exit 0
fi

echo "============================================"
echo "URSim + ROS2 Driver + RViz Startup"
echo "============================================"
echo ""
echo "Robot Type: $UR_TYPE"
echo "URSim Model: $ROBOT_MODEL"
echo "RViz: $LAUNCH_RVIZ"
echo ""

# -----------------------------------------------------------------------------
# Step 1: Ensure directories and URCap exist
# -----------------------------------------------------------------------------
echo "[1/4] Checking prerequisites..."

mkdir -p ${HOME}/.ursim/programs
mkdir -p ${HOME}/.ursim/urcaps

# Check if External Control URCap exists
if ! ls ${HOME}/.ursim/urcaps/externalcontrol*.jar 1>/dev/null 2>&1; then
    echo "      External Control URCap not found. Downloading..."
    URCAP_VERSION=1.0.5
    curl -L -o ${HOME}/.ursim/urcaps/externalcontrol-${URCAP_VERSION}.jar \
        https://github.com/UniversalRobots/Universal_Robots_ExternalControl_URCap/releases/download/v${URCAP_VERSION}/externalcontrol-${URCAP_VERSION}.jar
    echo "      Downloaded."
else
    echo "      External Control URCap found."
fi

# Check if ROS2 and ur_robot_driver are available
if ! command -v ros2 &> /dev/null; then
    echo "ERROR: ROS2 not found. Please source your ROS2 setup.bash"
    echo "  source /opt/ros/\$ROS_DISTRO/setup.bash"
    exit 1
fi

if ! ros2 pkg list 2>/dev/null | grep -q ur_robot_driver; then
    echo "ERROR: ur_robot_driver not found. Install it with:"
    echo "  sudo apt install ros-\${ROS_DISTRO}-ur-robot-driver"
    exit 1
fi

echo "      ROS2 and ur_robot_driver found."

# -----------------------------------------------------------------------------
# Step 2: Start URSim container
# -----------------------------------------------------------------------------
check_ursim_ready() {
    (echo > /dev/tcp/localhost/30001) 2>/dev/null
}

echo "[2/4] Starting URSim..."

# Check if URSim is already running
if docker ps --format '{{.Names}}' | grep -q "^${URSIM_CONTAINER}$"; then
    if check_ursim_ready; then
        echo "      URSim already running and ready."
    else
        echo "      URSim container exists but not ready, restarting..."
        docker rm -f "$URSIM_CONTAINER" 2>/dev/null || true
    fi
else
    # Remove stopped container if exists
    docker rm -f "$URSIM_CONTAINER" 2>/dev/null || true
fi

# Start URSim if not running
if ! docker ps --format '{{.Names}}' | grep -q "^${URSIM_CONTAINER}$"; then
    echo "      Starting URSim container in background..."
    docker run -d --rm \
        -p 5900:5900 \
        -p 6080:6080 \
        -p 29999:29999 \
        -p 30001:30001 \
        -p 30002:30002 \
        -p 30003:30003 \
        -p 30004:30004 \
        -v ${HOME}/.ursim/urcaps:/urcaps \
        -v ${HOME}/.ursim/programs:/ursim/programs \
        -e ROBOT_MODEL=${ROBOT_MODEL} \
        --name "$URSIM_CONTAINER" \
        universalrobots/ursim_e-series

    # Wait for URSim to be ready
    echo "      Waiting for URSim to be ready (this may take 30-60 seconds)..."
    TIMEOUT=120
    ELAPSED=0
    while ! check_ursim_ready; do
        if [ $ELAPSED -ge $TIMEOUT ]; then
            echo ""
            echo "ERROR: URSim failed to start within ${TIMEOUT}s"
            echo "Check logs with: docker logs $URSIM_CONTAINER"
            exit 1
        fi
        echo -n "."
        sleep 3
        ELAPSED=$((ELAPSED + 3))
    done
    echo " Ready!"
fi

# Get URSim container IP
ROBOT_IP=$(docker inspect "$URSIM_CONTAINER" --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
echo "      URSim IP: $ROBOT_IP"

# -----------------------------------------------------------------------------
# Step 3: Configure X11 for RViz
# -----------------------------------------------------------------------------
echo "[3/4] Configuring display..."
xhost +local:root 2>/dev/null || true

# -----------------------------------------------------------------------------
# Step 4: Launch ROS2 Driver
# -----------------------------------------------------------------------------
echo "[4/4] Launching ROS2 Driver..."
echo ""
echo "============================================"
echo "Setup Complete!"
echo "============================================"
echo ""
echo "URSim Web Interface: http://localhost:6080/vnc.html"
echo ""
echo "IMPORTANT - In URSim:"
echo "  1. Power ON the robot (red button -> ON -> START)"
echo "  2. Go to Installation -> URCaps -> External Control"
echo "     Set Host IP: $(hostname -I | awk '{print $1}')"
echo "     Set Port: 50002"
echo "  3. Create program: Program -> URCaps -> External Control"
echo "  4. Press PLAY (the driver will connect automatically)"
echo ""
echo "Useful commands:"
echo "  Stop URSim:       docker rm -f $URSIM_CONTAINER"
echo "  URSim logs:       docker logs -f $URSIM_CONTAINER"
echo "  Check topics:     ros2 topic list"
echo "  Joint states:     ros2 topic echo /joint_states"
echo ""
echo "============================================"
echo ""
echo "Launching ROS2 driver (Ctrl+C to stop)..."
echo ""

# Build launch command
LAUNCH_CMD="ros2 launch ur_robot_driver ur_control.launch.py \
    ur_type:=${UR_TYPE} \
    robot_ip:=${ROBOT_IP} \
    headless_mode:=true \
    launch_rviz:=${LAUNCH_RVIZ} \
    initial_joint_controller:=joint_trajectory_controller"

echo "Command: $LAUNCH_CMD"
echo ""

# Execute
exec $LAUNCH_CMD
