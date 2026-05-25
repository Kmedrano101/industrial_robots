#!/usr/bin/env bash
set -e
source /opt/ros/${ROS_DISTRO}/setup.bash      # ROS available to the FastAPI app
exec "$@"
