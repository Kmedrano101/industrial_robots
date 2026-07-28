# =============================================================================
# UR 3D Printer Web Interface - Multi-stage Dockerfile
# =============================================================================
# Stage 1: Build frontend (Node.js)
# Stage 2: Runtime (ROS2 + Python backend + static frontend)
# =============================================================================

ARG ROS_DISTRO=humble

# -----------------------------------------------------------------------------
# Stage 1: Frontend Build
# -----------------------------------------------------------------------------
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --ignore-scripts 2>/dev/null || npm install
COPY frontend/ ./
RUN npm run build

# -----------------------------------------------------------------------------
# Stage 2: Runtime (ROS2 + FastAPI backend)
# -----------------------------------------------------------------------------
FROM osrf/ros:${ROS_DISTRO}-desktop AS runtime

ARG ROS_DISTRO
ENV ROS_DISTRO=${ROS_DISTRO}
ENV DEBIAN_FRONTEND=noninteractive

# Install Python dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install CycloneDDS RMW + the message packages that the bridge subscribes
# to or whose service types it calls.
#  * ur-dashboard-msgs: RobotMode/SafetyMode subs + Trigger services
#  * trajectory-msgs:   JointTrajectory publisher for jog/move_to_home
#  * std-srvs:          shipped with desktop, listed for completeness
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-${ROS_DISTRO}-rmw-cyclonedds-cpp \
    ros-${ROS_DISTRO}-ur-dashboard-msgs \
    ros-${ROS_DISTRO}-trajectory-msgs \
    ros-${ROS_DISTRO}-controller-manager-msgs \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user. Newer osrf/ros:*-desktop images ship with an
# `ubuntu` user at UID/GID 1000, so we rename instead of creating fresh.
RUN if getent group 1000 >/dev/null; then \
        groupmod -n web "$(getent group 1000 | cut -d: -f1)"; \
    else \
        groupadd -g 1000 web; \
    fi && \
    if getent passwd 1000 >/dev/null; then \
        usermod -l web -d /home/web -m -g web "$(getent passwd 1000 | cut -d: -f1)" 2>/dev/null || true; \
        usermod -s /bin/bash web; \
    else \
        useradd -m -u 1000 -g web -s /bin/bash web; \
    fi

# Install Python packages. --break-system-packages is required on Noble
# (PEP 668 externally-managed) but does not exist on Jammy's pip (humble base),
# so detect support at build time and only pass it when available.
COPY backend/requirements.txt /tmp/requirements.txt
RUN BSP=$(pip3 install --help 2>&1 | grep -q -- --break-system-packages && echo --break-system-packages || true); \
    pip3 install --no-cache-dir $BSP -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Copy backend
WORKDIR /app
COPY backend/ /app/backend/

# Copy frontend build
COPY --from=frontend-build /app/frontend/dist /app/static

# Copy slicer modules from ur_3d_printer package (if available in context)
# These are imported by slicer_service.py
COPY --chown=web:web . /app/web_package/

# Create upload directory
RUN mkdir -p /uploads && chown web:web /uploads

# Environment defaults
ENV WEB_PORT=8090
ENV UPLOAD_DIR=/uploads
ENV STATIC_DIR=/app/static
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ENV PYTHONPATH=/app:/app/web_package

USER web

# Entrypoint: source ROS2 and start server
COPY --chown=web:web docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh 2>/dev/null || true

EXPOSE 8090

# Go through entrypoint.sh rather than sourcing ROS inline: it also selects
# the right CycloneDDS config, without which rclpy cannot create its node.
ENTRYPOINT ["/entrypoint.sh"]
CMD ["/bin/bash", "-c", "exec python3 -m uvicorn backend.main:app --host 0.0.0.0 --port ${WEB_PORT}"]
