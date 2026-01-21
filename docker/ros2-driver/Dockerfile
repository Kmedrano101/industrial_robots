# =============================================================================
# Universal Robots ROS2 Driver - Multi-Version Dockerfile
# =============================================================================
# Supports: humble, jazzy, rolling
# Usage: docker build --build-arg ROS_DISTRO=humble -t ur-ros2-driver:humble .
# =============================================================================

ARG ROS_DISTRO=humble
ARG BASE_IMAGE=ros

# -----------------------------------------------------------------------------
# Base Stage: ROS2 Foundation
# -----------------------------------------------------------------------------
FROM osrf/${BASE_IMAGE}:${ROS_DISTRO}-desktop AS base

ARG ROS_DISTRO
ENV ROS_DISTRO=${ROS_DISTRO}
ENV DEBIAN_FRONTEND=noninteractive

LABEL maintainer="your-email@example.com"
LABEL description="Universal Robots ROS2 Driver"
LABEL ros.distro="${ROS_DISTRO}"

# Install common dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    python3-pip \
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-vcstool \
    wget \
    curl \
    netcat-openbsd \
    iputils-ping \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# Driver Stage: Install UR Robot Driver
# -----------------------------------------------------------------------------
FROM base AS driver

ARG ROS_DISTRO

# Install UR Robot Driver from apt (if available for the distro)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-${ROS_DISTRO}-ur-robot-driver \
    ros-${ROS_DISTRO}-ur-moveit-config \
    ros-${ROS_DISTRO}-ur-description \
    ros-${ROS_DISTRO}-ur-msgs \
    ros-${ROS_DISTRO}-ur-controllers \
    ros-${ROS_DISTRO}-ur-calibration \
    ros-${ROS_DISTRO}-ur-dashboard-msgs \
    || echo "Some packages not available, will build from source" \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# Workspace Stage: Build from source (fallback/custom builds)
# -----------------------------------------------------------------------------
FROM driver AS workspace

ARG ROS_DISTRO
ARG BUILD_FROM_SOURCE=false

WORKDIR /ros2_ws

# Only build from source if packages aren't available or explicitly requested
RUN if [ "$BUILD_FROM_SOURCE" = "true" ]; then \
    mkdir -p src && \
    cd src && \
    git clone -b ${ROS_DISTRO} https://github.com/UniversalRobots/Universal_Robots_ROS2_Driver.git ur_robot_driver && \
    cd /ros2_ws && \
    . /opt/ros/${ROS_DISTRO}/setup.sh && \
    rosdep update && \
    rosdep install --from-paths src --ignore-src -r -y && \
    colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release; \
    fi

# -----------------------------------------------------------------------------
# Runtime Stage: Final Image
# -----------------------------------------------------------------------------
FROM workspace AS runtime

ARG ROS_DISTRO

# Create non-root user for security
ARG USERNAME=ros
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && apt-get update \
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME \
    && rm -rf /var/lib/apt/lists/*

# Setup entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create directories for calibration and configs
RUN mkdir -p /calibration /config && chown -R $USERNAME:$USERNAME /calibration /config

# Environment setup
ENV ROS_DOMAIN_ID=0
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# Install CycloneDDS for better performance
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-${ROS_DISTRO}-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /ros2_ws

USER $USERNAME

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
