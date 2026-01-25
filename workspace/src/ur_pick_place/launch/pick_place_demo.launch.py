#!/usr/bin/env python3
"""
Pick and Place Demo Launch File for URSim

Launches the pick and place nodes to work with the UR robot driver
running in the URSim Docker container.

Prerequisites:
    - URSim container running (docker compose --profile sim up)
    - UR driver connected to URSim
    - Kinematics server running

Usage:
    ros2 launch ur_pick_place pick_place_demo.launch.py
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, TimerAction, LogInfo
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # Package path
    ur_pick_place_share = FindPackageShare('ur_pick_place')

    # Config file
    pick_place_config = PathJoinSubstitution([
        ur_pick_place_share, 'config', 'pick_place.yaml'
    ])

    # Log info
    log_info = LogInfo(msg="""
    ============================================
    Pick and Place Demo for URSim
    ============================================

    This launch file starts the pick/place nodes.

    Prerequisites:
      1. URSim running: docker compose --profile sim up
      2. Robot program started in URSim (External Control)
      3. Kinematics server: ros2 launch ur_kinematics_node kinematics_server.launch.py

    To execute pick and place:
      ros2 service call /pick_place_node/pick_place ur_pick_place/srv/PickPlace "{}"

    To control gripper:
      ros2 service call /gripper_controller/set_gripper ur_pick_place/srv/SetGripper "{open: true}"
    ============================================
    """)

    # Gripper controller
    gripper_controller_node = Node(
        package='ur_pick_place',
        executable='gripper_controller',
        name='gripper_controller',
        output='screen',
        parameters=[pick_place_config],
    )

    # Pick and place node (delayed to allow services to be ready)
    pick_place_node = TimerAction(
        period=2.0,
        actions=[
            Node(
                package='ur_pick_place',
                executable='pick_place_node',
                name='pick_place_node',
                output='screen',
                parameters=[pick_place_config],
            )
        ]
    )

    return LaunchDescription([
        log_info,
        gripper_controller_node,
        pick_place_node,
    ])
