#!/bin/bash
# =============================================================================
# Start Pick and Place Demo with URSim
# =============================================================================
# This script properly starts the URSim simulation with RViz visualization
# for the pick and place demo.
#
# Usage: ./scripts/start_pick_place.sh
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "============================================"
echo "Pick and Place Demo Startup Script"
echo "============================================"
echo ""

# Allow X11 connections
echo "[1/4] Configuring X11 access..."
xhost +local:docker 2>/dev/null || true

# Check if URSim is already running and healthy
check_ursim_ready() {
    # Check from host using exposed port (no nc needed in container)
    (echo > /dev/tcp/localhost/30001) 2>/dev/null
}

if docker ps --format '{{.Names}}' | grep -q '^ursim$' && check_ursim_ready; then
    echo "[2/4] URSim already running and healthy, skipping restart..."
    URSIM_ALREADY_RUNNING=true
else
    URSIM_ALREADY_RUNNING=false
    # Stop existing containers
    echo "[2/4] Stopping existing containers..."
    docker compose --profile sim down 2>/dev/null || true
    sleep 2

    # Start containers with proper configuration
    echo "[3/4] Starting URSim and UR Driver containers..."
    docker compose --profile sim up -d
fi

# Wait for URSim to be ready (only if we started it fresh)
if [ "$URSIM_ALREADY_RUNNING" = false ]; then
    echo "[4/4] Waiting for URSim to be ready..."
    echo "      This may take up to 2 minutes..."

    TIMEOUT=120
    ELAPSED=0
    while ! check_ursim_ready; do
        if [ $ELAPSED -ge $TIMEOUT ]; then
            echo ""
            echo "Warning: URSim may not be fully ready (timeout after ${TIMEOUT}s)"
            break
        fi
        echo -n "."
        sleep 5
        ELAPSED=$((ELAPSED + 5))
    done
    echo ""
else
    echo "[3/4] Skipped (URSim already running)"
    echo "[4/4] Skipped (URSim already ready)"
fi

echo ""
echo "============================================"
echo "Setup Complete!"
echo "============================================"
echo ""
echo "URSim Web Interface: http://localhost:6080/vnc.html"
echo ""
echo "Next steps:"
echo "1. Open URSim web interface and start 'External Control' program"
echo "2. Build and run the pick_place demo inside the container:"
echo ""
echo "   docker exec -it ur-driver bash"
echo ""
echo "   # Inside container:"
echo "   cd /workspace"
echo "   source /opt/ros/jazzy/setup.bash"
echo "   colcon build --packages-select ur_pick_place"
echo "   source install/setup.bash"
echo "   ros2 launch ur_pick_place pick_place_ursim.launch.py launch_rviz:=false"
echo ""
echo "3. Test the gripper:"
echo "   ros2 service call /gripper_controller/set_gripper ur_pick_place/srv/SetGripper \"{open: false}\""
echo ""
echo "============================================"
