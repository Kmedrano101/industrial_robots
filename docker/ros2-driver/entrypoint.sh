#!/bin/bash
set -e

# =============================================================================
# Universal Robots ROS2 Driver Entrypoint
# =============================================================================

# Source ROS2 setup
if [ -f "/opt/ros/${ROS_DISTRO}/setup.bash" ]; then
    source "/opt/ros/${ROS_DISTRO}/setup.bash"
    echo "[entrypoint] Sourced ROS2 ${ROS_DISTRO}"
fi

# Source workspace if built from source
if [ -f "/ros2_ws/install/setup.bash" ]; then
    source "/ros2_ws/install/setup.bash"
    echo "[entrypoint] Sourced workspace overlay"
fi

# Set ROS_DOMAIN_ID if provided
if [ -n "${ROS_DOMAIN_ID}" ]; then
    export ROS_DOMAIN_ID=${ROS_DOMAIN_ID}
    echo "[entrypoint] ROS_DOMAIN_ID=${ROS_DOMAIN_ID}"
fi

# Configure DDS for Docker networking
export RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}
echo "[entrypoint] RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION}"

# Wait for robot if ROBOT_IP is set
if [ -n "${ROBOT_IP}" ]; then
    echo "[entrypoint] Waiting for robot at ${ROBOT_IP}..."
    timeout=60
    counter=0
    while ! nc -z ${ROBOT_IP} 30001 2>/dev/null; do
        counter=$((counter + 1))
        if [ $counter -ge $timeout ]; then
            echo "[entrypoint] WARNING: Robot not reachable after ${timeout}s, continuing anyway..."
            break
        fi
        sleep 1
    done
    if [ $counter -lt $timeout ]; then
        echo "[entrypoint] Robot is reachable!"
    fi
fi

# Execute command
exec "$@"
