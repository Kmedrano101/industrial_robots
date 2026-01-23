#!/usr/bin/env python3
"""
Launch file for the Target Follower Demo.

This launches:
1. UR5e robot driver with fake hardware
2. RViz with custom configuration
3. Target follower node for IK-based tracking
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    # Get package directories
    ur_driver_pkg = get_package_share_directory('ur_robot_driver')

    # Declare arguments
    ur_type_arg = DeclareLaunchArgument(
        'ur_type',
        default_value='ur5e',
        description='Type of UR robot'
    )

    pattern_arg = DeclareLaunchArgument(
        'pattern',
        default_value='circular',
        description='Movement pattern: circular (8-point loop) or scan (9-point zigzag)'
    )

    # Launch UR driver with fake hardware
    ur_control_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            ur_driver_pkg, '/launch/ur_control.launch.py'
        ]),
        launch_arguments={
            'ur_type': LaunchConfiguration('ur_type'),
            'robot_ip': 'xxx.xxx.xxx.xxx',
            'use_fake_hardware': 'true',
            'launch_rviz': 'false',
            'initial_joint_controller': 'joint_trajectory_controller',
        }.items()
    )

    # RViz node with custom config
    rviz_config = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'config',
        'target_follower.rviz'
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', rviz_config],
        output='screen'
    )

    # Target follower node (delayed start to ensure driver is ready)
    target_follower_node = TimerAction(
        period=5.0,  # Wait 5 seconds for driver to initialize
        actions=[
            Node(
                package='ur_kinematics_node',
                executable='target_follower',
                name='target_follower',
                output='screen',
                parameters=[{
                    'use_sim_time': False,
                    'pattern': LaunchConfiguration('pattern'),
                }]
            )
        ]
    )

    return LaunchDescription([
        ur_type_arg,
        pattern_arg,
        ur_control_launch,
        rviz_node,
        target_follower_node,
    ])
