#!/bin/bash
# =============================================================================
# Check ROS2 Topics from UR Driver
# =============================================================================
# Quick diagnostic script to verify the UR driver is publishing data
# =============================================================================

echo "============================================"
echo "ROS2 UR Driver Diagnostic"
echo "============================================"
echo ""

# Check if ur-driver container is running
if ! docker ps --format '{{.Names}}' | grep -q '^ur-driver$'; then
    echo "ERROR: ur-driver container is not running"
    echo "Start it with: ./scripts/start_ursim_rviz.sh"
    exit 1
fi

echo "1. Checking ROS2 nodes..."
docker exec ur-driver bash -c 'source /opt/ros/$ROS_DISTRO/setup.bash && ros2 node list' 2>/dev/null || echo "   No nodes found"

echo ""
echo "2. Checking ROS2 topics..."
docker exec ur-driver bash -c 'source /opt/ros/$ROS_DISTRO/setup.bash && ros2 topic list' 2>/dev/null || echo "   No topics found"

echo ""
echo "3. Checking joint_states topic frequency..."
timeout 5 docker exec ur-driver bash -c 'source /opt/ros/$ROS_DISTRO/setup.bash && ros2 topic hz /joint_states --window 10' 2>/dev/null || echo "   No joint_states published (External Control may not be running in URSim)"

echo ""
echo "4. Controller status..."
docker exec ur-driver bash -c 'source /opt/ros/$ROS_DISTRO/setup.bash && ros2 control list_controllers' 2>/dev/null || echo "   Cannot get controller status"

echo ""
echo "============================================"
echo "If joint_states shows 0 Hz or no frequency:"
echo "  -> Make sure External Control is running in URSim"
echo "============================================"
