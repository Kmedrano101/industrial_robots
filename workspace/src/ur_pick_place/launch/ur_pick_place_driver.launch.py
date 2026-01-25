#!/usr/bin/env python3
"""
UR Pick and Place Driver Launch File

This launch file starts the UR robot driver with a custom robot description
that includes the workcell (table, gripper, objects) for visualization in RViz.

It uses the official ur_control.launch.py with a custom description_launchfile
that includes the pick and place scene.

Usage:
    ros2 launch ur_pick_place ur_pick_place_driver.launch.py robot_ip:=<URSIM_IP>

Arguments:
    ur_type: Robot type (default: ur5e)
    robot_ip: Robot IP address (default: 172.17.0.2 for Docker URSim)
    launch_rviz: Launch RViz (default: true)
    headless_mode: Headless mode for driver (default: true)
"""

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
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
    # =========================================================================
    # Arguments
    # =========================================================================
    ur_type_arg = DeclareLaunchArgument(
        'ur_type',
        default_value='ur5e',
        description='Type of UR robot (ur3e, ur5e, ur10e, ur16e, ur20, ur30)'
    )

    robot_ip_arg = DeclareLaunchArgument(
        'robot_ip',
        default_value='172.17.0.2',
        description='IP address of the robot (URSim or real robot)'
    )

    launch_rviz_arg = DeclareLaunchArgument(
        'launch_rviz',
        default_value='true',
        description='Launch RViz with workcell visualization'
    )

    headless_mode_arg = DeclareLaunchArgument(
        'headless_mode',
        default_value='true',
        description='Run driver in headless mode (no teach pendant needed)'
    )

    include_gripper_arg = DeclareLaunchArgument(
        'include_gripper',
        default_value='true',
        description='Include gripper in robot description'
    )

    include_objects_arg = DeclareLaunchArgument(
        'include_objects',
        default_value='true',
        description='Include pick/place objects in scene'
    )

    # =========================================================================
    # Package paths
    # =========================================================================
    ur_pick_place_share = FindPackageShare('ur_pick_place')
    ur_robot_driver_share = FindPackageShare('ur_robot_driver')

    # =========================================================================
    # Custom description launchfile path
    # =========================================================================
    description_launchfile = PathJoinSubstitution([
        ur_pick_place_share, 'launch', 'ur_pick_place_rsp.launch.py'
    ])

    # =========================================================================
    # Include UR Control Launch (official driver)
    # =========================================================================
    ur_control_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                ur_robot_driver_share, 'launch', 'ur_control.launch.py'
            ])
        ]),
        launch_arguments={
            'ur_type': LaunchConfiguration('ur_type'),
            'robot_ip': LaunchConfiguration('robot_ip'),
            'headless_mode': LaunchConfiguration('headless_mode'),
            'launch_rviz': 'false',  # We launch our own RViz with custom config
            'description_launchfile': description_launchfile,
            'initial_joint_controller': 'joint_trajectory_controller',
        }.items(),
    )

    # =========================================================================
    # Pick and Place nodes
    # =========================================================================
    pick_place_config = PathJoinSubstitution([
        ur_pick_place_share, 'config', 'pick_place.yaml'
    ])

    gripper_controller_node = Node(
        package='ur_pick_place',
        executable='gripper_controller',
        name='gripper_controller',
        output='screen',
        parameters=[pick_place_config],
        condition=IfCondition(LaunchConfiguration('include_gripper')),
    )

    # Pick and place node (delayed to allow driver to connect)
    pick_place_node = TimerAction(
        period=8.0,
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

    # =========================================================================
    # RViz with custom config
    # =========================================================================
    rviz_config = PathJoinSubstitution([
        ur_pick_place_share, 'config', 'pick_place.rviz'
    ])

    rviz_node = TimerAction(
        period=5.0,  # Delay RViz start to allow driver to initialize
        actions=[
            Node(
                package='rviz2',
                executable='rviz2',
                name='rviz2',
                output='screen',
                arguments=['-d', rviz_config],
            )
        ]
    )

    # =========================================================================
    # Info message
    # =========================================================================
    log_info = LogInfo(msg="""
    ============================================================
    UR Pick and Place Workcell Driver
    ============================================================

    Starting UR robot driver with custom workcell description.

    The workcell includes:
      - UR robot arm
      - Industrial table
      - Parallel gripper
      - Pick/place objects

    IMPORTANT - In URSim:
      1. Power ON the robot (red button -> ON -> START)
      2. Configure External Control URCap:
         Installation -> URCaps -> External Control
         Set Host IP to your machine's IP
      3. Create program with External Control node
      4. Press PLAY

    Commands:
      # Execute pick and place
      ros2 service call /pick_place_node/pick_place ur_pick_place/srv/PickPlace "{}"

      # Control gripper
      ros2 service call /gripper_controller/set_gripper ur_pick_place/srv/SetGripper "{open: true}"

      # Check topics
      ros2 topic echo /joint_states

    ============================================================
    """)

    # =========================================================================
    # Launch Description
    # =========================================================================
    return LaunchDescription([
        # Arguments
        ur_type_arg,
        robot_ip_arg,
        launch_rviz_arg,
        headless_mode_arg,
        include_gripper_arg,
        include_objects_arg,

        # Info
        log_info,

        # UR Control (includes robot_state_publisher, controllers, etc.)
        ur_control_launch,

        # Pick and place nodes
        gripper_controller_node,
        pick_place_node,

        # Visualization
        rviz_node,
    ])
