#!/usr/bin/env python3
"""
Pick and Place Demo Launch File for URSim Integration

This launch file provides visualization of the workstation (table + gripper)
alongside the UR robot controlled via URSim.

Prerequisites:
    - URSim container running (docker compose --profile sim up)
    - UR driver connected to URSim
    - External Control program started in URSim

Usage (run inside ur-driver container):
    ros2 launch ur_pick_place pick_place_ursim.launch.py

Or from host after building workspace:
    ros2 launch ur_pick_place pick_place_ursim.launch.py
"""

import os
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    TimerAction,
    LogInfo,
    OpaqueFunction,
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
    launch_rviz_arg = DeclareLaunchArgument(
        'launch_rviz',
        default_value='true',
        description='Launch RViz for visualization'
    )

    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='Use simulation time'
    )

    # Package paths
    ur_pick_place_share = FindPackageShare('ur_pick_place')

    # Config files
    pick_place_config = PathJoinSubstitution([
        ur_pick_place_share, 'config', 'pick_place.yaml'
    ])

    rviz_config = PathJoinSubstitution([
        ur_pick_place_share, 'config', 'pick_place.rviz'
    ])

    # Log info
    log_info = LogInfo(msg="""
    ============================================
    Pick and Place Demo for URSim
    ============================================

    This launch starts visualization and pick/place nodes
    that integrate with the UR robot driver.

    Prerequisites:
      1. URSim running: docker compose --profile sim up
      2. Robot program started in URSim (External Control)
      3. This launch file running in same ROS2 network as ur-driver

    To execute pick and place:
      ros2 service call /pick_place_node/pick_place ur_pick_place/srv/PickPlace "{}"

    To control gripper:
      ros2 service call /gripper_controller/set_gripper ur_pick_place/srv/SetGripper "{open: true}"
    ============================================
    """)

    # Static transform: world -> base_link (table mount offset)
    # This places the robot on the table at 0.92m height
    static_tf_world_base = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='world_to_base_link',
        arguments=[
            '--x', '0.0',
            '--y', '0.0',
            '--z', '0.92',  # Table height (0.9m) + mounting plate (0.02m)
            '--roll', '0.0',
            '--pitch', '0.0',
            '--yaw', '0.0',
            '--frame-id', 'world',
            '--child-frame-id', 'base_link',
        ],
    )

    # Table visualization (static URDF)
    table_description = Command([
        FindExecutable(name='xacro'), ' ',
        PathJoinSubstitution([
            ur_pick_place_share, 'urdf', 'industrial_table.urdf.xacro'
        ]),
        ' ', 'standalone:=true',
    ])

    table_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='table_state_publisher',
        namespace='table',
        parameters=[{
            'robot_description': table_description,
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
        remappings=[
            ('/joint_states', '/table/joint_states'),
        ],
    )

    # Gripper description (attached to tool0)
    gripper_description = Command([
        FindExecutable(name='xacro'), ' ',
        PathJoinSubstitution([
            ur_pick_place_share, 'urdf', 'parallel_gripper.urdf.xacro'
        ]),
        ' ', 'standalone:=true',
    ])

    gripper_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='gripper_state_publisher',
        namespace='gripper',
        parameters=[{
            'robot_description': gripper_description,
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
        remappings=[
            ('/joint_states', '/gripper_joint_states'),
        ],
    )

    # Static transform: tool0 -> gripper_mount (connects robot to gripper)
    static_tf_tool_gripper = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='tool0_to_gripper',
        arguments=[
            '--x', '0.0',
            '--y', '0.0',
            '--z', '0.0',
            '--roll', '0.0',
            '--pitch', '0.0',
            '--yaw', '0.0',
            '--frame-id', 'tool0',
            '--child-frame-id', 'gripper_mount',
        ],
    )

    # Gripper controller (simulated)
    gripper_controller_node = Node(
        package='ur_pick_place',
        executable='gripper_controller',
        name='gripper_controller',
        output='screen',
        parameters=[pick_place_config, {
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
    )

    # Pick and place node (delayed to allow services to be ready)
    pick_place_node = TimerAction(
        period=3.0,
        actions=[
            Node(
                package='ur_pick_place',
                executable='pick_place_node',
                name='pick_place_node',
                output='screen',
                parameters=[pick_place_config, {
                    'use_sim_time': LaunchConfiguration('use_sim_time'),
                }],
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
        parameters=[{
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
        condition=IfCondition(LaunchConfiguration('launch_rviz')),
    )

    return LaunchDescription([
        # Arguments
        launch_rviz_arg,
        use_sim_time_arg,

        # Info
        log_info,

        # Static transforms and state publishers
        static_tf_world_base,
        table_state_publisher,
        gripper_state_publisher,
        static_tf_tool_gripper,

        # Application nodes
        gripper_controller_node,
        pick_place_node,

        # Visualization
        rviz_node,
    ])
