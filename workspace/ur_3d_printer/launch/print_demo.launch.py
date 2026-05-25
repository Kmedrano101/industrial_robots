#!/usr/bin/env python3
# Copyright 2024 Kevin Medrano
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Full 3D Printer Demo Launch File

Complete launch with UR robot driver integration, kinematics server,
extruder controller, print node, and visualization.

Prerequisites:
    - ur_description, ur_robot_driver packages installed
    - Robot or URSim accessible

Usage:
    ros2 launch ur_3d_printer print_demo.launch.py robot_ip:=192.168.1.100
"""

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    TimerAction,
)
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
    ur_type_arg = DeclareLaunchArgument(
        'ur_type', default_value='ur5e', description='UR robot type'
    )
    robot_ip_arg = DeclareLaunchArgument(
        'robot_ip', default_value='192.168.56.101', description='Robot IP address'
    )
    launch_rviz_arg = DeclareLaunchArgument(
        'launch_rviz', default_value='true', description='Launch RViz'
    )
    extruder_type_arg = DeclareLaunchArgument(
        'extruder_type', default_value='fdm', description='Extruder type (fdm/paste)'
    )

    # Package paths
    ur_3d_printer_share = FindPackageShare('ur_3d_printer')

    # Robot description
    robot_description_content = Command([
        FindExecutable(name='xacro'), ' ',
        PathJoinSubstitution([
            ur_3d_printer_share, 'urdf', 'ur_3d_printer_cell.urdf.xacro'
        ]),
        ' ', 'ur_type:=', LaunchConfiguration('ur_type'),
        ' ', 'extruder_type:=', LaunchConfiguration('extruder_type'),
        ' ', 'robot_ip:=', LaunchConfiguration('robot_ip'),
    ])
    robot_description = {'robot_description': robot_description_content}

    # Config files
    print_config = PathJoinSubstitution([
        ur_3d_printer_share, 'config', 'print_params.yaml'
    ])
    rviz_config = PathJoinSubstitution([
        ur_3d_printer_share, 'config', 'printer_3d.rviz'
    ])

    # Robot State Publisher
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[robot_description],
    )

    # Extruder controller
    extruder_controller_node = Node(
        package='ur_3d_printer',
        executable='extruder_controller',
        name='extruder_controller',
        output='screen',
        parameters=[print_config],
    )

    # Toolpath visualizer
    toolpath_visualizer_node = Node(
        package='ur_3d_printer',
        executable='toolpath_visualizer',
        name='toolpath_visualizer',
        output='screen',
    )

    # Print node (delayed)
    print_node = TimerAction(
        period=5.0,
        actions=[
            Node(
                package='ur_3d_printer',
                executable='print_node',
                name='print_node',
                output='screen',
                parameters=[print_config],
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
        ur_type_arg,
        robot_ip_arg,
        launch_rviz_arg,
        extruder_type_arg,
        robot_state_publisher_node,
        extruder_controller_node,
        toolpath_visualizer_node,
        print_node,
        rviz_node,
    ])
