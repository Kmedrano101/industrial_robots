#!/bin/bash
# =============================================================================
# Build Docker Images for UR + ROS2
# =============================================================================
# Usage: ./build.sh [ros_distro]
# Example: ./build.sh humble
#          ./build.sh jazzy
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Default ROS distro
ROS_DISTRO=${1:-${ROS_DISTRO:-humble}}

echo "=============================================="
echo "  Building UR + ROS2 Docker Images"
echo "  ROS Distro: ${ROS_DISTRO}"
echo "=============================================="

cd "$PROJECT_DIR"

# Build URSim image
echo ""
echo "[1/2] Building URSim image..."
docker compose build ursim

# Build ROS2 Driver image
echo ""
echo "[2/2] Building ROS2 Driver image (${ROS_DISTRO})..."
ROS_DISTRO=${ROS_DISTRO} docker compose build ur-driver

echo ""
echo "=============================================="
echo "  Build Complete!"
echo "=============================================="
echo ""
echo "Images created:"
docker images | grep -E "ur-ursim|ur-ros2-driver" | head -5
echo ""
echo "To start simulation:"
echo "  docker compose --profile sim up"
echo ""
