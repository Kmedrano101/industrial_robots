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
Robot State Publisher for UR 3D Printer Workcell.

Used as the description_launchfile for ur_robot_driver so the driver
publishes the full workcell URDF (robot + extruder + print bed).

The arguments mirror those declared by ur_control.launch.py and are
passed through verbatim, exactly as ur_pick_place_rsp.launch.py does.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import (
    Command,
    FindExecutable,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    # ── Values passed in by ur_control.launch.py ──────────────────────────────
    ur_type = LaunchConfiguration('ur_type')
    robot_ip = LaunchConfiguration('robot_ip')
    tf_prefix = LaunchConfiguration('tf_prefix')

    safety_limits = LaunchConfiguration('safety_limits')
    safety_pos_margin = LaunchConfiguration('safety_pos_margin')
    safety_k_position = LaunchConfiguration('safety_k_position')

    kinematics_params_file = LaunchConfiguration('kinematics_params_file')
    physical_params_file = LaunchConfiguration('physical_params_file')
    visual_params_file = LaunchConfiguration('visual_params_file')
    joint_limit_params_file = LaunchConfiguration('joint_limit_params_file')

    use_mock_hardware = LaunchConfiguration('use_mock_hardware')
    mock_sensor_commands = LaunchConfiguration('mock_sensor_commands')
    headless_mode = LaunchConfiguration('headless_mode')

    use_tool_communication = LaunchConfiguration('use_tool_communication')
    tool_voltage = LaunchConfiguration('tool_voltage')
    tool_parity = LaunchConfiguration('tool_parity')
    tool_baud_rate = LaunchConfiguration('tool_baud_rate')
    tool_stop_bits = LaunchConfiguration('tool_stop_bits')
    tool_rx_idle_chars = LaunchConfiguration('tool_rx_idle_chars')
    tool_tx_idle_chars = LaunchConfiguration('tool_tx_idle_chars')
    tool_device_name = LaunchConfiguration('tool_device_name')
    tool_tcp_port = LaunchConfiguration('tool_tcp_port')

    reverse_ip = LaunchConfiguration('reverse_ip')
    script_command_port = LaunchConfiguration('script_command_port')
    reverse_port = LaunchConfiguration('reverse_port')
    script_sender_port = LaunchConfiguration('script_sender_port')
    trajectory_port = LaunchConfiguration('trajectory_port')

    # ── Scene options (3D printer specific) ───────────────────────────────────
    extruder_type = LaunchConfiguration('extruder_type')
    include_bed = LaunchConfiguration('include_bed')

    # ── Driver script / recipe paths ──────────────────────────────────────────
    script_filename = PathJoinSubstitution([
        FindPackageShare('ur_client_library'), 'resources', 'external_control.urscript',
    ])
    input_recipe_filename = PathJoinSubstitution([
        FindPackageShare('ur_robot_driver'), 'resources', 'rtde_input_recipe.txt',
    ])
    output_recipe_filename = PathJoinSubstitution([
        FindPackageShare('ur_robot_driver'), 'resources', 'rtde_output_recipe.txt',
    ])

    ur_3d_printer_share = FindPackageShare('ur_3d_printer')

    # ── Full workcell URDF ────────────────────────────────────────────────────
    robot_description_content = Command([
        FindExecutable(name='xacro'), ' ',
        PathJoinSubstitution([
            ur_3d_printer_share, 'urdf', 'ur_3d_printer_cell.urdf.xacro'
        ]),
        ' ', 'ur_type:=', ur_type,
        ' ', 'tf_prefix:=', tf_prefix,
        ' ', 'joint_limit_params:=', joint_limit_params_file,
        ' ', 'kinematics_params:=', kinematics_params_file,
        ' ', 'physical_params:=', physical_params_file,
        ' ', 'visual_params:=', visual_params_file,
        ' ', 'safety_limits:=', safety_limits,
        ' ', 'safety_pos_margin:=', safety_pos_margin,
        ' ', 'safety_k_position:=', safety_k_position,
        ' ', 'robot_ip:=', robot_ip,
        ' ', 'script_filename:=', script_filename,
        ' ', 'input_recipe_filename:=', input_recipe_filename,
        ' ', 'output_recipe_filename:=', output_recipe_filename,
        ' ', 'use_mock_hardware:=', use_mock_hardware,
        ' ', 'mock_sensor_commands:=', mock_sensor_commands,
        ' ', 'headless_mode:=', headless_mode,
        ' ', 'use_tool_communication:=', use_tool_communication,
        ' ', 'tool_voltage:=', tool_voltage,
        ' ', 'tool_parity:=', tool_parity,
        ' ', 'tool_baud_rate:=', tool_baud_rate,
        ' ', 'tool_stop_bits:=', tool_stop_bits,
        ' ', 'tool_rx_idle_chars:=', tool_rx_idle_chars,
        ' ', 'tool_tx_idle_chars:=', tool_tx_idle_chars,
        ' ', 'tool_device_name:=', tool_device_name,
        ' ', 'tool_tcp_port:=', tool_tcp_port,
        ' ', 'reverse_ip:=', reverse_ip,
        ' ', 'script_command_port:=', script_command_port,
        ' ', 'reverse_port:=', reverse_port,
        ' ', 'script_sender_port:=', script_sender_port,
        ' ', 'trajectory_port:=', trajectory_port,
        ' ', 'extruder_type:=', extruder_type,
        ' ', 'include_bed:=', include_bed,
    ])

    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': ParameterValue(robot_description_content, value_type=str),
        }],
    )

    # ── Declare all arguments (with defaults matching ur_control.launch.py) ───
    declared_arguments = [
        DeclareLaunchArgument('ur_type', default_value='ur7e'),
        DeclareLaunchArgument('robot_ip', default_value='0.0.0.0'),
        DeclareLaunchArgument('tf_prefix', default_value=''),
        DeclareLaunchArgument('safety_limits', default_value='true'),
        DeclareLaunchArgument('safety_pos_margin', default_value='0.15'),
        DeclareLaunchArgument('safety_k_position', default_value='20'),
        DeclareLaunchArgument('joint_limit_params_file', default_value=PathJoinSubstitution([
            FindPackageShare('ur_description'), 'config', ur_type, 'joint_limits.yaml'
        ])),
        DeclareLaunchArgument('kinematics_params_file', default_value=PathJoinSubstitution([
            FindPackageShare('ur_description'), 'config', ur_type, 'default_kinematics.yaml'
        ])),
        DeclareLaunchArgument('physical_params_file', default_value=PathJoinSubstitution([
            FindPackageShare('ur_description'), 'config', ur_type, 'physical_parameters.yaml'
        ])),
        DeclareLaunchArgument('visual_params_file', default_value=PathJoinSubstitution([
            FindPackageShare('ur_description'), 'config', ur_type, 'visual_parameters.yaml'
        ])),
        DeclareLaunchArgument('use_mock_hardware', default_value='false'),
        DeclareLaunchArgument('mock_sensor_commands', default_value='false'),
        DeclareLaunchArgument('headless_mode', default_value='false'),
        DeclareLaunchArgument('use_tool_communication', default_value='false'),
        DeclareLaunchArgument('tool_voltage', default_value='0'),
        DeclareLaunchArgument('tool_parity', default_value='0'),
        DeclareLaunchArgument('tool_baud_rate', default_value='115200'),
        DeclareLaunchArgument('tool_stop_bits', default_value='1'),
        DeclareLaunchArgument('tool_rx_idle_chars', default_value='1.5'),
        DeclareLaunchArgument('tool_tx_idle_chars', default_value='3.5'),
        DeclareLaunchArgument('tool_device_name', default_value='/tmp/ttyUR'),
        DeclareLaunchArgument('tool_tcp_port', default_value='54321'),
        DeclareLaunchArgument('reverse_ip', default_value='0.0.0.0'),
        DeclareLaunchArgument('script_command_port', default_value='50004'),
        DeclareLaunchArgument('reverse_port', default_value='50001'),
        DeclareLaunchArgument('script_sender_port', default_value='50002'),
        DeclareLaunchArgument('trajectory_port', default_value='50003'),
        # 3D printer scene options
        DeclareLaunchArgument('extruder_type', default_value='fdm',
                              description='Extruder type: fdm or paste'),
        DeclareLaunchArgument('include_bed', default_value='true',
                              description='Include print bed in scene'),
    ]

    return LaunchDescription(declared_arguments + [robot_state_publisher_node])
