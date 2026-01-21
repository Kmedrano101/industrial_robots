#!/bin/bash
# =============================================================================
# Check Status of UR + ROS2 Stack
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_DIR"

echo "=============================================="
echo "  UR + ROS2 Stack Status"
echo "=============================================="
echo ""

echo "Docker Containers:"
echo "-------------------------------------------"
docker compose ps -a 2>/dev/null || echo "No containers running"
echo ""

echo "Docker Networks:"
echo "-------------------------------------------"
docker network ls | grep ur-network || echo "Network not created"
echo ""

echo "Docker Volumes:"
echo "-------------------------------------------"
docker volume ls | grep -E "ursim|ur-driver" || echo "No volumes"
echo ""

# Check if URSim is reachable
URSIM_IP=${URSIM_IP:-172.28.0.10}
echo "URSim Connectivity (${URSIM_IP}):"
echo "-------------------------------------------"
for port in 29999 30001 30004; do
    if nc -z -w1 $URSIM_IP $port 2>/dev/null; then
        echo "  Port $port: OK"
    else
        echo "  Port $port: Not reachable"
    fi
done
echo ""

# Check ROS2 topics if driver is running
if docker ps | grep -q ur-driver; then
    echo "ROS2 Topics:"
    echo "-------------------------------------------"
    docker exec ur-driver bash -c "source /opt/ros/\${ROS_DISTRO}/setup.bash && ros2 topic list 2>/dev/null | head -10" || echo "Cannot list topics"
fi
