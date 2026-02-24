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
3D Printer Launch File for URSim (App-Level).

Launches the 3D printer application nodes alongside a UR robot driver
that is already running (e.g. started via print_driver.launch.py or
ur_control.launch.py in a separate container).

This mirrors pick_place_ursim.launch.py: it does NOT start the driver,
it only adds the workcell visualization and application nodes on top of
an existing /joint_states + /joint_trajectory_controller action.

Prerequisites:
    1. URSim running:  docker compose --profile sim up
    2. UR driver connected to URSim and External Control program running
    3. Kinematics server OR pass robot_model so this launch starts one

Usage:
    ros2 launch ur_3d_printer print_ursim.launch.py

    # Preload a G-code file in RViz:
    ros2 launch ur_3d_printer print_ursim.launch.py \
        gcode_file:=/path/to/your.gcode

    # Skip RViz (e.g. headless server):
    ros2 launch ur_3d_printer print_ursim.launch.py launch_rviz:=false

Start a print:
    ros2 service call /print_node/start_print ur_3d_printer/srv/StartPrint \
        "{gcode_filepath: '/path/to/your.gcode'}"
"""

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    TimerAction,
    LogInfo,
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
    # ── Arguments ─────────────────────────────────────────────────────────────
    launch_rviz_arg = DeclareLaunchArgument(
        'launch_rviz', default_value='true', description='Launch RViz'
    )
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time', default_value='false', description='Use simulation time'
    )
    robot_model_arg = DeclareLaunchArgument(
        'robot_model', default_value='ur5e',
        description='UR robot model for the kinematics server'
    )
    gcode_file_arg = DeclareLaunchArgument(
        'gcode_file', default_value='',
        description='G-code file to preload for toolpath visualization'
    )

    # ── Package paths ──────────────────────────────────────────────────────────
    ur_3d_printer_share = FindPackageShare('ur_3d_printer')

    # ── Config files ───────────────────────────────────────────────────────────
    print_config = PathJoinSubstitution([
        ur_3d_printer_share, 'config', 'print_params.yaml'
    ])
    rviz_config = PathJoinSubstitution([
        ur_3d_printer_share, 'config', 'printer_3d.rviz'
    ])

    # ── Static TF: world → base_link (table mount at 0.92 m) ─────────────────
    static_tf_world_base = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='world_to_base_link',
        arguments=[
            '--x', '0.0', '--y', '0.0', '--z', '0.92',
            '--roll', '0.0', '--pitch', '0.0', '--yaw', '0.0',
            '--frame-id', 'world', '--child-frame-id', 'base_link',
        ],
    )

    # ── Extruder visualization (separate RSP in extruder namespace) ───────────
    extruder_description = Command([
        FindExecutable(name='xacro'), ' ',
        PathJoinSubstitution([
            ur_3d_printer_share, 'urdf', 'fdm_extruder.urdf.xacro'
        ]),
        ' ', 'standalone:=true',
    ])

    extruder_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='extruder_state_publisher',
        namespace='extruder',
        parameters=[{
            'robot_description': extruder_description,
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
    )

    # ── Static TF: tool0 → extruder_mount ────────────────────────────────────
    static_tf_tool_extruder = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='tool0_to_extruder',
        arguments=[
            '--x', '0.0', '--y', '0.0', '--z', '0.0',
            '--roll', '0.0', '--pitch', '0.0', '--yaw', '0.0',
            '--frame-id', 'tool0', '--child-frame-id', 'extruder_mount',
        ],
    )

    # ── Print bed visualization (separate RSP in print_bed namespace) ─────────
    bed_description = Command([
        FindExecutable(name='xacro'), ' ',
        PathJoinSubstitution([
            ur_3d_printer_share, 'urdf', 'print_bed.urdf.xacro'
        ]),
        ' ', 'standalone:=true',
    ])

    bed_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='bed_state_publisher',
        namespace='print_bed',
        parameters=[{
            'robot_description': bed_description,
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
    )

    # ── Kinematics server (IK/FK/Jacobian for print_node) ────────────────────
    kinematics_server_node = Node(
        package='ur_kinematics_node',
        executable='kinematics_server',
        name='ur_kinematics_server',
        output='screen',
        parameters=[{
            'robot_model': LaunchConfiguration('robot_model'),
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
    )

    # ── Extruder controller ───────────────────────────────────────────────────
    extruder_controller_node = Node(
        package='ur_3d_printer',
        executable='extruder_controller',
        name='extruder_controller',
        output='screen',
        parameters=[print_config, {
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
    )

    # ── Toolpath visualizer ───────────────────────────────────────────────────
    toolpath_visualizer_node = Node(
        package='ur_3d_printer',
        executable='toolpath_visualizer',
        name='toolpath_visualizer',
        output='screen',
        parameters=[print_config, {
            'frame_id': 'world',
            'publish_rate': 2.0,
            'gcode_file': LaunchConfiguration('gcode_file'),
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
    )

    # ── Print node (delayed — allow kinematics server to start) ───────────────
    print_node = TimerAction(
        period=3.0,
        actions=[
            Node(
                package='ur_3d_printer',
                executable='print_node',
                name='print_node',
                output='screen',
                parameters=[print_config, {
                    'use_sim_time': LaunchConfiguration('use_sim_time'),
                }],
            )
        ]
    )

    # ── RViz ──────────────────────────────────────────────────────────────────
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
        parameters=[{'use_sim_time': LaunchConfiguration('use_sim_time')}],
        condition=IfCondition(LaunchConfiguration('launch_rviz')),
    )

    log_info = LogInfo(msg=r"""
    ============================================
    UR 3D Printer — URSim App Launch
    ============================================

    Prerequisites:
      1. URSim running:  docker compose --profile sim up
      2. External Control program running in URSim
      3. UR driver connected (ur_control.launch.py or print_driver.launch.py)

    Start a print:
      ros2 service call /print_node/start_print \
        ur_3d_printer/srv/StartPrint \
        "{gcode_filepath: '/path/to/file.gcode'}"

    Calibrate origin from current TCP pose:
      ros2 service call /print_node/calibrate_origin \
        ur_3d_printer/srv/CalibrateOrigin "{use_current_pose: true}"
    ============================================
    """)

    return LaunchDescription([
        launch_rviz_arg,
        use_sim_time_arg,
        robot_model_arg,
        gcode_file_arg,
        log_info,
        static_tf_world_base,
        extruder_state_publisher,
        static_tf_tool_extruder,
        bed_state_publisher,
        kinematics_server_node,
        extruder_controller_node,
        toolpath_visualizer_node,
        print_node,
        rviz_node,
    ])
