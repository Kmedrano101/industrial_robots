#!/usr/bin/env python3
"""
Standalone runner for the Target Follower Demo.

Usage:
    1. Start the UR driver with fake hardware:
       docker run -d --rm --name ur-driver-fake \
         --network robots_ur-network \
         -e ROS_DOMAIN_ID=10 \
         -e DISPLAY=:1 \
         -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
         ur-ros2-driver:humble \
         bash -c "source /opt/ros/humble/setup.bash && \
           ros2 launch ur_robot_driver ur_control.launch.py \
           ur_type:=ur5e robot_ip:=xxx use_fake_hardware:=true \
           launch_rviz:=true initial_joint_controller:=joint_trajectory_controller"

    2. Run this script from the ros2-dev container:
       docker exec -it ros2-dev bash
       export ROS_DOMAIN_ID=10
       source /opt/ros/humble/setup.bash
       source /home/ros/workspace/install/setup.bash
       python3 /home/ros/workspace/src/ur_kinematics_node/run_target_follower.py
"""

import subprocess
import time
import sys
import os

def main():
    print("=" * 70)
    print("  Target Follower Demo - Screw Theory IK Real-Time Tracking")
    print("=" * 70)
    print()
    print("This demo shows real-time IK tracking where the robot follows")
    print("a moving target through 3 waypoints.")
    print()
    print("Prerequisites:")
    print("  1. UR driver running with fake hardware (see docstring)")
    print("  2. RViz should show the target markers")
    print()
    print("Press Ctrl+C to stop the demo.")
    print("=" * 70)
    print()

    # Add the package path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # Import and run the target follower
    from ur_kinematics_node.target_follower import main as follower_main

    follower_main()


if __name__ == '__main__':
    main()
