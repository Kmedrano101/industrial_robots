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
UR 3D Printer - Full Driver Launch File

Starts the UR robot driver with the custom 3D printer workcell description
(robot + FDM extruder + print bed), then brings up the kinematics server,
extruder controller, toolpath visualizer, and print node.

Usage:
    # Against URSim (Docker default IP):
    ros2 launch ur_3d_printer print_driver.launch.py robot_ip:=172.17.0.2

    # Against a real robot:
    ros2 launch ur_3d_printer print_driver.launch.py robot_ip:=192.168.1.100

    # With a preloaded G-code file shown in RViz:
    ros2 launch ur_3d_printer print_driver.launch.py \
        robot_ip:=172.17.0.2 \
        gcode_file:=/path/to/your.gcode

Prerequisites (URSim):
    1. docker compose --profile sim up
    2. Power ON robot in URSim teach pendant
    3. Installation -> URCaps -> External Control -> set Host IP
    4. Load program with External Control node and press PLAY

After launch, start a print:
    ros2 service call /print_node/start_print ur_3d_printer/srv/StartPrint \
        "{gcode_filepath: '/path/to/your.gcode'}"
"""

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    OpaqueFunction,
    TimerAction,
    LogInfo,
)
from launch.conditions import IfCondition
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # ── Arguments ─────────────────────────────────────────────────────────────
    ur_type_arg = DeclareLaunchArgument(
        'ur_type', default_value='ur7e',
        description='UR robot model (ur3e, ur5e, ur7e, ur10e, ur16e, ur20, ur30)'
    )
    robot_ip_arg = DeclareLaunchArgument(
        'robot_ip', default_value='172.17.0.2',
        description='IP address of the robot or URSim container'
    )
    headless_mode_arg = DeclareLaunchArgument(
        'headless_mode', default_value='true',
        description='Run driver headless (no teach pendant required)'
    )
    launch_rviz_arg = DeclareLaunchArgument(
        'launch_rviz', default_value='true',
        description='Launch RViz with workcell visualization'
    )
    extruder_type_arg = DeclareLaunchArgument(
        'extruder_type', default_value='fdm',
        description='Extruder type: fdm or paste'
    )
    gcode_file_arg = DeclareLaunchArgument(
        'gcode_file', default_value='',
        description='G-code file to preload for toolpath visualization in RViz'
    )
    kinematics_params_file_arg = DeclareLaunchArgument(
        'kinematics_params_file', default_value='',
        description=(
            'Path to a YAML produced by ur_calibration with the connected '
            'robots calibration data. Strongly recommended on real hardware; '
            'omit (empty) to fall back to the nominal model calibration '
            '(TCP may be off by centimetres).'
        ),
    )

    # ── Package paths ──────────────────────────────────────────────────────────
    ur_3d_printer_share = FindPackageShare('ur_3d_printer')
    ur_robot_driver_share = FindPackageShare('ur_robot_driver')

    # ── Custom RSP as description_launchfile ───────────────────────────────────
    description_launchfile = PathJoinSubstitution([
        ur_3d_printer_share, 'launch', 'ur_3d_printer_rsp.launch.py'
    ])

    # ── UR Control (official driver) ──────────────────────────────────────────
    # Build the launch-arguments dict at runtime so we can resolve the
    # kinematics file once and pass a concrete value down.
    #
    # We must ALWAYS pass kinematics_params_file. This launch declares the
    # argument with an empty default, and an empty LaunchConfiguration of the
    # same name leaks into the included ur_control.launch.py (and the RSP) via
    # launch scoping — overriding ur_control's own per-model default. xacro
    # then receives an empty kinematics_params and falls back to a
    # non-existent 'ur5x/default_kinematics.yaml', crashing the launch. When no
    # calibration file is supplied we therefore substitute the nominal
    # per-model kinematics shipped with ur_description.
    def _ur_control_launch_factory(context):
        ur_type = LaunchConfiguration('ur_type').perform(context)
        args = {
            'ur_type': ur_type,
            'robot_ip': LaunchConfiguration('robot_ip').perform(context),
            'headless_mode': LaunchConfiguration('headless_mode').perform(context),
            'launch_rviz': 'false',          # Use our custom RViz config
            'description_launchfile': description_launchfile.perform(context),
            'initial_joint_controller': 'joint_trajectory_controller',
            'extruder_type': LaunchConfiguration('extruder_type').perform(context),
        }
        kpf = LaunchConfiguration('kinematics_params_file').perform(context).strip()
        if not kpf:
            kpf = PathJoinSubstitution([
                FindPackageShare('ur_description'), 'config', ur_type,
                'default_kinematics.yaml',
            ]).perform(context)
        args['kinematics_params_file'] = kpf
        return [IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                PathJoinSubstitution([
                    ur_robot_driver_share, 'launch', 'ur_control.launch.py'
                ]).perform(context)
            ]),
            launch_arguments=args.items(),
        )]

    ur_control_launch = OpaqueFunction(function=_ur_control_launch_factory)

    # ── Config ─────────────────────────────────────────────────────────────────
    print_config = PathJoinSubstitution([
        ur_3d_printer_share, 'config', 'print_params.yaml'
    ])
    rviz_config = PathJoinSubstitution([
        ur_3d_printer_share, 'config', 'printer_3d.rviz'
    ])

    # ── Kinematics server ─────────────────────────────────────────────────────
    kinematics_server_node = Node(
        package='ur_kinematics_node',
        executable='kinematics_server',
        name='ur_kinematics_server',
        output='screen',
        parameters=[{'robot_model': LaunchConfiguration('ur_type')}],
    )

    # ── Extruder controller ───────────────────────────────────────────────────
    extruder_controller_node = Node(
        package='ur_3d_printer',
        executable='extruder_controller',
        name='extruder_controller',
        output='screen',
        parameters=[print_config],
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
        }],
    )

    # ── Deposition visualizer (3D material rendering in RViz) ──────────────────
    deposition_visualizer_node = Node(
        package='ur_3d_printer',
        executable='deposition_visualizer',
        name='deposition_visualizer',
        output='screen',
        parameters=[print_config, {
            'frame_id': 'world',
            'demo_mode': True,
            'speed_scale': 5.0,
            'publish_rate': 30.0,
            'color_scheme': 'pla',
            'gcode_file': LaunchConfiguration('gcode_file'),
        }],
    )

    # ── Print node (delayed — driver needs time to connect to robot) ──────────
    print_node = TimerAction(
        period=8.0,
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

    # ── RViz (delayed — wait for robot_description + TF to be ready) ─────────
    rviz_node = TimerAction(
        period=5.0,
        actions=[
            Node(
                package='rviz2',
                executable='rviz2',
                name='rviz2',
                output='screen',
                arguments=['-d', rviz_config],
                condition=IfCondition(LaunchConfiguration('launch_rviz')),
            )
        ]
    )

    # ── Startup instructions ───────────────────────────────────────────────────
    log_info = LogInfo(msg=r"""
    ============================================================
    UR 3D Printer — Driver Launch
    ============================================================

    Starting UR robot driver with 3D printer workcell (robot +
    extruder + print bed).

    IMPORTANT — In URSim (or on the teach pendant):
      1. Power ON the robot
      2. Installation -> URCaps -> External Control
         Set Host IP to this machine's IP address
      3. Load a program with an External Control node
      4. Press PLAY

    Once the driver is connected, start a print:
      ros2 service call /print_node/start_print \
        ur_3d_printer/srv/StartPrint \
        "{gcode_filepath: '/path/to/your.gcode'}"

    Calibrate print origin from current TCP pose:
      ros2 service call /print_node/calibrate_origin \
        ur_3d_printer/srv/CalibrateOrigin "{use_current_pose: true}"
    ============================================================
    """)

    return LaunchDescription([
        ur_type_arg,
        robot_ip_arg,
        headless_mode_arg,
        launch_rviz_arg,
        extruder_type_arg,
        gcode_file_arg,
        kinematics_params_file_arg,
        log_info,
        # UR driver (includes robot_state_publisher, controllers, TF)
        ur_control_launch,
        # Printer app nodes
        kinematics_server_node,
        extruder_controller_node,
        toolpath_visualizer_node,
        deposition_visualizer_node,
        print_node,
        # Visualization
        rviz_node,
    ])
