#!/usr/bin/env python3
"""
Standalone Pick and Place Demo Launch File

Launches a simplified demo without requiring ur_robot_driver or ur_description.
Uses joint_state_publisher for joint state publishing.

For full demo with UR robot driver, use pick_place_demo.launch.py
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, TimerAction
from launch.conditions import IfCondition
from launch.substitutions import (
    Command,
    FindExecutable,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # Arguments
    launch_rviz_arg = DeclareLaunchArgument(
        'launch_rviz',
        default_value='true',
        description='Launch RViz'
    )

    # Package paths
    ur_pick_place_share = FindPackageShare('ur_pick_place')

    # Robot description from standalone xacro
    robot_description_content = Command([
        FindExecutable(name='xacro'), ' ',
        PathJoinSubstitution([
            ur_pick_place_share, 'urdf', 'pick_place_standalone.urdf.xacro'
        ]),
    ])

    robot_description = {'robot_description': robot_description_content}

    # Config files
    pick_place_config = PathJoinSubstitution([
        ur_pick_place_share, 'config', 'pick_place.yaml'
    ])

    rviz_config = PathJoinSubstitution([
        ur_pick_place_share, 'config', 'pick_place.rviz'
    ])

    # Robot State Publisher
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[robot_description],
    )

    # Joint State Publisher (built-in, publishes robot + gripper joint states)
    joint_state_publisher_node = Node(
        package='ur_pick_place',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        output='screen',
        parameters=[{'publish_rate': 50.0}],
    )

    # Gripper controller
    gripper_controller_node = Node(
        package='ur_pick_place',
        executable='gripper_controller',
        name='gripper_controller',
        output='screen',
        parameters=[pick_place_config],
    )

    # Pick and place node (delayed)
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

    # RViz
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
        condition=IfCondition(LaunchConfiguration('launch_rviz')),
    )

    return LaunchDescription([
        # Arguments
        launch_rviz_arg,

        # Nodes
        robot_state_publisher_node,
        joint_state_publisher_node,
        gripper_controller_node,
        pick_place_node,
        rviz_node,
    ])
