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
exec "$@"
