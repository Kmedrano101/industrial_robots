#!/usr/bin/env bash
set -e
# Pick the DDS config before ROS is touched — with the wrong one the rclpy
# bridge cannot create its node and the backend exits during startup.
# The script is mounted in by docker-compose: it is shared with ur-printer
# and lives outside this image's build context. Tolerate its absence so the
# image still runs standalone, just without the automatic fallback.
if [ -f /usr/local/bin/select-dds-config.sh ]; then
  source /usr/local/bin/select-dds-config.sh
fi
source /opt/ros/${ROS_DISTRO}/setup.bash      # ROS available to the FastAPI app

# Overlay the ur_3d_printer / ur_kinematics_msgs interfaces copied from the
# ur-printer image (see Dockerfile). Without this overlay the bridge cannot
# import the custom msg/srv types and quietly runs with no print telemetry
# and no print service clients.
if [ -f /ros2_ws/install/setup.bash ]; then
  source /ros2_ws/install/setup.bash
fi

exec "$@"
