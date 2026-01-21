<div align="center">

# Industrial Robots

### Multi-Brand Robotic Arm Integration with ROS2

[![ROS2](https://img.shields.io/badge/ROS2-Humble%20|%20Jazzy%20|%20Rolling-blue?style=for-the-badge&logo=ros)](https://docs.ros.org/)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Universal Robots](https://img.shields.io/badge/Universal%20Robots-Supported-red?style=for-the-badge)](https://www.universal-robots.com/)

<p align="center">
  <strong>A unified framework for controlling industrial robotic arms from multiple manufacturers using ROS2</strong>
</p>

---

[Getting Started](#-getting-started) •
[Features](#-features) •
[Supported Robots](#-supported-robots) •
[Documentation](#-documentation) •
[Contributing](#-contributing)

</div>

---

## Overview

**Industrial Robots** is a comprehensive, containerized solution for integrating and controlling industrial robotic arms from various manufacturers within the ROS2 ecosystem. This project provides a unified interface for simulation and real-world deployment, enabling seamless development and testing workflows.

---

## Features

| Feature | Description |
|---------|-------------|
| **Multi-Brand Support** | Unified interface for robots from Universal Robots, and more |
| **ROS2 Integration** | Full support for Humble, Jazzy, and Rolling distributions |
| **Containerized Stack** | Complete Docker-based deployment - no host ROS2 installation required |
| **Simulation Ready** | Integrated simulators for safe development and testing |
| **Real Robot Control** | Same codebase works for simulation and physical robots |
| **Modular Architecture** | Easy to extend with additional robot brands and models |

---

## Supported Robots

<table>
<tr>
<td align="center" width="33%">

### Universal Robots
**UR3e | UR5e | UR10e | UR16e | UR20 | UR30**

URSim integration included

</td>
<td align="center" width="33%">

### Coming Soon
**ABB | FANUC | KUKA**

Additional brands in development

</td>
<td align="center" width="33%">

### Custom Integration
**Your Robot Here**

Extensible architecture

</td>
</tr>
</table>

---

## Getting Started

### Prerequisites

| Requirement | Version |
|-------------|---------|
| Docker | 20.10+ |
| Docker Compose | v2+ |
| Disk Space | ~8GB |

### Quick Start

```bash
# Clone the repository
git clone https://github.com/Kmedrano101/industrial_robots.git
cd industrial_robots

# Build the Docker images
./docker/scripts/build.sh

# Start simulation environment
./docker/scripts/start.sh sim

# Access URSim web interface
# Open http://localhost:6080 in your browser
```

---

## Usage

### Simulation Mode

Launch the complete simulation stack including URSim and ROS2 drivers:

```bash
# Using Docker Compose
docker compose --profile sim up

# Or using the helper script
./docker/scripts/start.sh sim
```

Access the URSim interface at **http://localhost:6080**

### Real Robot Mode

Connect to a physical robot:

```bash
# Configure robot IP address
echo "ROBOT_IP=192.168.1.100" >> .env

# Launch the driver
./docker/scripts/start.sh real --robot-ip 192.168.1.100
```

### Switch ROS2 Distribution

```bash
# Build for a specific ROS2 version
ROS_DISTRO=jazzy ./docker/scripts/build.sh

# Run with the specified version
ROS_DISTRO=jazzy docker compose --profile sim up
```

---

## Configuration

Create your environment configuration:

```bash
cp .env.example .env
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ROS_DISTRO` | `humble` | ROS2 distribution version |
| `ROBOT_IP` | `172.28.0.10` | Target robot IP address |
| `UR_TYPE` | `ur5e` | Universal Robots model type |
| `ROBOT_MODEL` | `UR5` | URSim robot model |

---

## Project Structure

```
industrial_robots/
├── docker-compose.yml          # Container orchestration
├── .env                        # Environment configuration
├── docker/
│   ├── ros2-driver/            # ROS2 driver container
│   ├── ursim/                  # URSim container
│   └── scripts/                # Build and launch scripts
├── config/                     # Robot configurations
├── programs/                   # Robot programs (URScript, etc.)
├── workspace/                  # ROS2 development workspace
└── docs/                       # Extended documentation
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Quick Setup Guide](docs/QUICK_SETUP.md) | Step-by-step installation |
| [Network Architecture](docs/NETWORK_ARCHITECTURE.md) | Network configuration details |
| [Docker Architecture](docs/DOCKER_ARCHITECTURE.md) | Container structure overview |

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**Built for the robotics community**

</div>
