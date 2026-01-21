FROM universalrobots/ursim_e-series

# ============================================================================
# IMPORTANT: Do NOT override the ENTRYPOINT - this will prevent the simulator
# from starting properly.
# ============================================================================

# Install the URCap (external control for ROS/external drivers)
COPY externalcontrol-1.0.5.urcap /urcaps/externalcontrol-1.0.5.jar

# Install pre-made robot programs
COPY programs ursim/programs

# ============================================================================
# USAGE EXAMPLES:
# ============================================================================
#
# Build:
#   docker build -t ursim-extended .
#
# Run with default settings (UR5):
#   docker run --rm -it ursim-extended
#
# Select robot model (UR3, UR5, UR7, UR8LONG, UR10, UR12, UR15, UR16, UR18, UR20, UR30):
#   docker run --rm -it -e ROBOT_MODEL=UR10 ursim-extended
#
# Expose client interface ports to host:
#   Dashboard server:      -p 29999:29999
#   Primary interface:     -p 30001:30001
#   Secondary interface:   -p 30002:30002
#   Real-time interface:   -p 30003:30003
#   RTDE interface:        -p 30004:30004
#
# Example with UR10 and dashboard exposed:
#   docker run --rm -it -e ROBOT_MODEL=UR10 -p 29999:29999 ursim-extended
#
# ============================================================================
