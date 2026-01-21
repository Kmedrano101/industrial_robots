# =============================================================================
# Universal Robots Simulator (URSim) - Extended Image
# =============================================================================
# Includes External Control URCap pre-installed
# =============================================================================

ARG URSIM_VERSION=latest
FROM universalrobots/ursim_e-series:${URSIM_VERSION}

LABEL maintainer="your-email@example.com"
LABEL description="URSim with External Control URCap"

# =============================================================================
# IMPORTANT: Do NOT override the ENTRYPOINT - this will prevent the simulator
# from starting properly.
# =============================================================================

# Install External Control URCap
ARG URCAP_VERSION=1.0.5
ADD https://github.com/UniversalRobots/Universal_Robots_ExternalControl_URCap/releases/download/v${URCAP_VERSION}/externalcontrol-${URCAP_VERSION}.jar /urcaps/externalcontrol-${URCAP_VERSION}.jar

# Copy any custom programs (optional, can be bind-mounted instead)
# COPY programs /ursim/programs

# =============================================================================
# Environment Variables (can be overridden at runtime)
# =============================================================================
# ROBOT_MODEL: UR3, UR5, UR7, UR10, UR12, UR15, UR16, UR20, UR30
# =============================================================================
