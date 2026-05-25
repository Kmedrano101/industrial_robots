# Headless control-PC image: UR driver + ur_3d_printer workspace, NO GUI.
  ARG ROS_DISTRO=humble
  FROM ros:${ROS_DISTRO}-ros-base AS base
  ARG ROS_DISTRO
  ENV ROS_DISTRO=${ROS_DISTRO}
  ENV DEBIAN_FRONTEND=noninteractive

# Build tools + UR driver + CycloneDDS + slicing python deps
  RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake git \
        python3-pip python3-colcon-common-extensions python3-rosdep python3-vcstool \
        netcat-openbsd iputils-ping net-tools \
        ros-${ROS_DISTRO}-ur-robot-driver \
        ros-${ROS_DISTRO}-ur-description \
        ros-${ROS_DISTRO}-ur-calibration \
        ros-${ROS_DISTRO}-rmw-cyclonedds-cpp \
        ros-${ROS_DISTRO}-xacro \
        ros-${ROS_DISTRO}-robot-state-publisher \
        python3-numpy \
      && rm -rf /var/lib/apt/lists/*

  RUN pip3 install --no-cache-dir numpy-stl trimesh scipy

  # Build the workspace; --skip-keys rviz2 (RViz runs on the viz PC)
  WORKDIR /ros2_ws
  COPY workspace ./src
  RUN . /opt/ros/${ROS_DISTRO}/setup.sh \
      && rosdep update \
      && rosdep install --from-paths src --ignore-src -r -y --skip-keys "rviz2" \
      && colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release

  COPY docker/ros2-printer/entrypoint.sh /entrypoint.sh
  RUN chmod +x /entrypoint.sh
  ENTRYPOINT ["/entrypoint.sh"]
  CMD ["bash"]
