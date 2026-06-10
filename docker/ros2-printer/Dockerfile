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
        pybind11-dev libeigen3-dev \
      && rm -rf /var/lib/apt/lists/*

  # --break-system-packages is required on Noble (PEP 668 externally-managed)
  # but does not exist on Jammy's pip (humble base), so detect support at build
  # time and only pass it when available.
  RUN BSP=$(pip3 install --help 2>&1 | grep -q -- --break-system-packages && echo --break-system-packages || true); \
      pip3 install --no-cache-dir $BSP \
        numpy-stl trimesh scipy shapely

  # Build the workspace.
  # --skip-keys list:
  #   * rviz2          — runs on the viz PC, not needed in the headless image
  #   * python3-shapely — apt package missing on Noble base; installed via
  #     pip3 above (works inside the container regardless)
  #   * pybind11       — rosdep key not defined for jazzy; the package is
  #     pulled by the ur_screw_kinematics CMakeLists via find_package
  WORKDIR /ros2_ws
  COPY workspace ./src
  RUN . /opt/ros/${ROS_DISTRO}/setup.sh \
      && rosdep update \
      && rosdep install --from-paths src --ignore-src -r -y \
            --skip-keys "rviz2 python3-shapely pybind11" \
      && colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release

  COPY docker/ros2-printer/entrypoint.sh /entrypoint.sh
  COPY docker/ros2-printer/extract_calibration.sh /usr/local/bin/extract_calibration.sh
  RUN chmod +x /entrypoint.sh /usr/local/bin/extract_calibration.sh
  ENTRYPOINT ["/entrypoint.sh"]
  CMD ["bash"]
