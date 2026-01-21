#!/bin/bash
# =============================================================================
# Stop UR + ROS2 Stack
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_DIR"

echo "Stopping all UR + ROS2 containers..."
docker compose --profile sim --profile real --profile dev --profile full --profile viz down

echo "Done!"
