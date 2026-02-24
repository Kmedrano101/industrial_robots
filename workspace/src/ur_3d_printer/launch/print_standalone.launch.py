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
r"""
Standalone 3D Printer Demo Launch File

Launches a full standalone simulation without requiring ur_robot_driver.
The mock trajectory controller replays joint trajectories as joint state
publications so RViz shows the robot following the print toolpath.

Usage:
    ros2 launch ur_3d_printer print_standalone.launch.py
    ros2 launch ur_3d_printer print_standalone.launch.py speed_scale:=5.0
    ros2 launch ur_3d_printer print_standalone.launch.py launch_rviz:=false

After launch, start a print:
    ros2 service call /print_node/start_print ur_3d_printer/srv/StartPrint \
        "{gcode_filepath: '/path/to/your.gcode'}"
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
    # ── Arguments ─────────────────────────────────────────────────────────────
    launch_rviz_arg = DeclareLaunchArgument(
        'launch_rviz', default_value='true', description='Launch RViz'
    )
    robot_model_arg = DeclareLaunchArgument(
        'robot_model', default_value='ur5e',
        description='UR robot model (ur3e, ur5e, ur10e, ur16e, ur20, ur30)'
    )
    speed_scale_arg = DeclareLaunchArgument(
        'speed_scale', default_value='1.0',
        description='Trajectory playback speed multiplier (e.g. 5.0 = 5x faster)'
    )
    gcode_file_arg = DeclareLaunchArgument(
        'gcode_file', default_value='',
        description='G-code file to preload for toolpath visualization'
    )

    # ── Package paths ──────────────────────────────────────────────────────────
    ur_3d_printer_share = FindPackageShare('ur_3d_printer')

    # ── Robot description ──────────────────────────────────────────────────────
    robot_description_content = Command([
        FindExecutable(name='xacro'), ' ',
        PathJoinSubstitution([
            ur_3d_printer_share, 'urdf', 'printer_standalone.urdf.xacro'
        ]),
    ])
    robot_description = {'robot_description': robot_description_content}

    # ── Config files ───────────────────────────────────────────────────────────
    print_config = PathJoinSubstitution([
        ur_3d_printer_share, 'config', 'print_params.yaml'
    ])
    rviz_config = PathJoinSubstitution([
        ur_3d_printer_share, 'config', 'printer_3d.rviz'
    ])

    # ── Nodes ──────────────────────────────────────────────────────────────────

    # Robot State Publisher (publishes TF from joint states + URDF)
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[robot_description],
    )

    # Kinematics server — provides IK/FK/Jacobian services used by print_node
    kinematics_server_node = Node(
        package='ur_kinematics_node',
        executable='kinematics_server',
        name='ur_kinematics_server',
        output='screen',
        parameters=[{'robot_model': LaunchConfiguration('robot_model')}],
    )

    # Mock trajectory controller — serves FollowJointTrajectory action and
    # replays trajectories as /joint_states so RViz animates the robot.
    mock_controller_node = Node(
        package='ur_3d_printer',
        executable='mock_controller',
        name='mock_trajectory_controller',
        output='screen',
        parameters=[{
            'publish_rate': 50.0,
            'speed_scale': LaunchConfiguration('speed_scale'),
        }],
    )

    # Extruder controller (topic-based in standalone)
    extruder_controller_node = Node(
        package='ur_3d_printer',
        executable='extruder_controller',
        name='extruder_controller',
        output='screen',
        parameters=[print_config],
    )

    # Toolpath visualizer — publishes colored line strips of the toolpath.
    # If gcode_file is provided, the full path is shown immediately in RViz.
    toolpath_visualizer_node = Node(
        package='ur_3d_printer',
        executable='toolpath_visualizer',
        name='toolpath_visualizer',
        output='screen',
        parameters=[print_config, {
            'frame_id': 'world',
            'publish_rate': 2.0,
            'gcode_file': LaunchConfiguration('gcode_file'),
        }],
    )

    # Print node — delayed to allow kinematics server and mock controller
    # to be fully ready before IK service calls begin
    print_node = TimerAction(
        period=3.0,
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
        launch_rviz_arg,
        robot_model_arg,
        speed_scale_arg,
        gcode_file_arg,
        robot_state_publisher_node,
        kinematics_server_node,
        mock_controller_node,
        extruder_controller_node,
        toolpath_visualizer_node,
        print_node,
        rviz_node,
    ])
