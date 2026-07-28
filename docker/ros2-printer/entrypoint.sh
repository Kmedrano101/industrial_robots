#!/usr/bin/env bash
set -e
# Pick the DDS config before anything ROS-related starts: with the wrong one,
# creating a node fails outright. See select-dds-config.sh for why this has
# to be runtime detection rather than a single static file.
source /usr/local/bin/select-dds-config.sh
source /opt/ros/${ROS_DISTRO}/setup.bash      # base ROS
source /ros2_ws/install/setup.bash            # your built workspace overlay
exec "$@"
