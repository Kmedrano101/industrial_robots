#!/usr/bin/env python3
"""
Robot State Publisher for UR Pick Place Workcell

This launch file is used as the description_launchfile for ur_robot_driver.
It publishes the custom workcell URDF (robot + table + gripper + objects).

The arguments match those expected by ur_control.launch.py so they can be
passed through from the driver launch file.
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
    # =========================================================================
    # Launch Configurations (get values passed from ur_control.launch.py)
    # =========================================================================
    ur_type = LaunchConfiguration("ur_type")
    robot_ip = LaunchConfiguration("robot_ip")
    tf_prefix = LaunchConfiguration("tf_prefix")

    # Safety parameters
    safety_limits = LaunchConfiguration("safety_limits")
    safety_pos_margin = LaunchConfiguration("safety_pos_margin")
    safety_k_position = LaunchConfiguration("safety_k_position")

    # Parameter files
    kinematics_params_file = LaunchConfiguration("kinematics_params_file")
    physical_params_file = LaunchConfiguration("physical_params_file")
    visual_params_file = LaunchConfiguration("visual_params_file")
    joint_limit_params_file = LaunchConfiguration("joint_limit_params_file")

    # ros2_control parameters
    use_mock_hardware = LaunchConfiguration("use_mock_hardware")
    mock_sensor_commands = LaunchConfiguration("mock_sensor_commands")
    headless_mode = LaunchConfiguration("headless_mode")

    # Tool communication
    use_tool_communication = LaunchConfiguration("use_tool_communication")
    tool_voltage = LaunchConfiguration("tool_voltage")
    tool_parity = LaunchConfiguration("tool_parity")
    tool_baud_rate = LaunchConfiguration("tool_baud_rate")
    tool_stop_bits = LaunchConfiguration("tool_stop_bits")
    tool_rx_idle_chars = LaunchConfiguration("tool_rx_idle_chars")
    tool_tx_idle_chars = LaunchConfiguration("tool_tx_idle_chars")
    tool_device_name = LaunchConfiguration("tool_device_name")
    tool_tcp_port = LaunchConfiguration("tool_tcp_port")

    # Communication ports
    reverse_ip = LaunchConfiguration("reverse_ip")
    script_command_port = LaunchConfiguration("script_command_port")
    reverse_port = LaunchConfiguration("reverse_port")
    script_sender_port = LaunchConfiguration("script_sender_port")
    trajectory_port = LaunchConfiguration("trajectory_port")

    # Scene options
    include_gripper = LaunchConfiguration("include_gripper")
    include_objects = LaunchConfiguration("include_objects")
    include_table = LaunchConfiguration("include_table")

    # =========================================================================
    # Script and recipe file paths (from ur_robot_driver)
    # =========================================================================
    script_filename = PathJoinSubstitution([
        FindPackageShare("ur_client_library"),
        "resources",
        "external_control.urscript",
    ])
    input_recipe_filename = PathJoinSubstitution([
        FindPackageShare("ur_robot_driver"),
        "resources",
        "rtde_input_recipe.txt"
    ])
    output_recipe_filename = PathJoinSubstitution([
        FindPackageShare("ur_robot_driver"),
        "resources",
        "rtde_output_recipe.txt"
    ])

    # =========================================================================
    # Package paths
    # =========================================================================
    ur_pick_place_share = FindPackageShare('ur_pick_place')

    # =========================================================================
    # Robot description from custom URDF
    # =========================================================================
    robot_description_content = Command([
        FindExecutable(name='xacro'), ' ',
        PathJoinSubstitution([
            ur_pick_place_share, 'urdf', 'ur_pick_place_cell.urdf.xacro'
        ]),
        # Robot type and prefix
        ' ', 'ur_type:=', ur_type,
        ' ', 'tf_prefix:=', tf_prefix,
        # Parameter files
        ' ', 'joint_limit_params:=', joint_limit_params_file,
        ' ', 'kinematics_params:=', kinematics_params_file,
        ' ', 'physical_params:=', physical_params_file,
        ' ', 'visual_params:=', visual_params_file,
        # Safety
        ' ', 'safety_limits:=', safety_limits,
        ' ', 'safety_pos_margin:=', safety_pos_margin,
        ' ', 'safety_k_position:=', safety_k_position,
        # ros2_control
        ' ', 'robot_ip:=', robot_ip,
        ' ', 'script_filename:=', script_filename,
        ' ', 'input_recipe_filename:=', input_recipe_filename,
        ' ', 'output_recipe_filename:=', output_recipe_filename,
        ' ', 'use_mock_hardware:=', use_mock_hardware,
        ' ', 'mock_sensor_commands:=', mock_sensor_commands,
        ' ', 'headless_mode:=', headless_mode,
        # Tool communication
        ' ', 'use_tool_communication:=', use_tool_communication,
        ' ', 'tool_voltage:=', tool_voltage,
        ' ', 'tool_parity:=', tool_parity,
        ' ', 'tool_baud_rate:=', tool_baud_rate,
        ' ', 'tool_stop_bits:=', tool_stop_bits,
        ' ', 'tool_rx_idle_chars:=', tool_rx_idle_chars,
        ' ', 'tool_tx_idle_chars:=', tool_tx_idle_chars,
        ' ', 'tool_device_name:=', tool_device_name,
        ' ', 'tool_tcp_port:=', tool_tcp_port,
        # Communication ports
        ' ', 'reverse_ip:=', reverse_ip,
        ' ', 'script_command_port:=', script_command_port,
        ' ', 'reverse_port:=', reverse_port,
        ' ', 'script_sender_port:=', script_sender_port,
        ' ', 'trajectory_port:=', trajectory_port,
        # Scene options
        ' ', 'include_gripper:=', include_gripper,
        ' ', 'include_objects:=', include_objects,
        ' ', 'include_table:=', include_table,
    ])

    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': ParameterValue(robot_description_content, value_type=str),
        }],
    )

    # =========================================================================
    # Declare Arguments (with defaults matching ur_control.launch.py)
    # =========================================================================
    declared_arguments = []

    # UR specific arguments
    declared_arguments.append(DeclareLaunchArgument(
        'ur_type',
        default_value='ur5e',
        description='Type of UR robot'
    ))
    declared_arguments.append(DeclareLaunchArgument(
        'robot_ip',
        default_value='0.0.0.0',
        description='IP address of the robot'
    ))
    declared_arguments.append(DeclareLaunchArgument(
        'tf_prefix',
        default_value='',
        description='TF prefix for joint names'
    ))

    # Safety parameters
    declared_arguments.append(DeclareLaunchArgument(
        'safety_limits',
        default_value='true',
        description='Enable safety limits controller'
    ))
    declared_arguments.append(DeclareLaunchArgument(
        'safety_pos_margin',
        default_value='0.15',
        description='Safety controller position margin'
    ))
    declared_arguments.append(DeclareLaunchArgument(
        'safety_k_position',
        default_value='20',
        description='Safety controller k-position factor'
    ))

    # Parameter files
    declared_arguments.append(DeclareLaunchArgument(
        'joint_limit_params_file',
        default_value=PathJoinSubstitution([
            FindPackageShare('ur_description'), 'config', ur_type, 'joint_limits.yaml'
        ]),
        description='Joint limit params file'
    ))
    declared_arguments.append(DeclareLaunchArgument(
        'kinematics_params_file',
        default_value=PathJoinSubstitution([
            FindPackageShare('ur_description'), 'config', ur_type, 'default_kinematics.yaml'
        ]),
        description='Kinematics params file'
    ))
    declared_arguments.append(DeclareLaunchArgument(
        'physical_params_file',
        default_value=PathJoinSubstitution([
            FindPackageShare('ur_description'), 'config', ur_type, 'physical_parameters.yaml'
        ]),
        description='Physical params file'
    ))
    declared_arguments.append(DeclareLaunchArgument(
        'visual_params_file',
        default_value=PathJoinSubstitution([
            FindPackageShare('ur_description'), 'config', ur_type, 'visual_parameters.yaml'
        ]),
        description='Visual params file'
    ))

    # ros2_control parameters
    declared_arguments.append(DeclareLaunchArgument(
        'use_mock_hardware',
        default_value='false',
        description='Use mock hardware interface'
    ))
    declared_arguments.append(DeclareLaunchArgument(
        'mock_sensor_commands',
        default_value='false',
        description='Mock sensor commands'
    ))
    declared_arguments.append(DeclareLaunchArgument(
        'headless_mode',
        default_value='false',
        description='Run in headless mode'
    ))

    # Tool communication
    declared_arguments.append(DeclareLaunchArgument(
        'use_tool_communication',
        default_value='false',
        description='Use tool communication'
    ))
    declared_arguments.append(DeclareLaunchArgument(
        'tool_voltage',
        default_value='0',
        description='Tool voltage'
    ))
    declared_arguments.append(DeclareLaunchArgument(
        'tool_parity',
        default_value='0',
        description='Tool parity'
    ))
    declared_arguments.append(DeclareLaunchArgument(
        'tool_baud_rate',
        default_value='115200',
        description='Tool baud rate'
    ))
    declared_arguments.append(DeclareLaunchArgument(
        'tool_stop_bits',
        default_value='1',
        description='Tool stop bits'
    ))
    declared_arguments.append(DeclareLaunchArgument(
        'tool_rx_idle_chars',
        default_value='1.5',
        description='Tool RX idle chars'
    ))
    declared_arguments.append(DeclareLaunchArgument(
        'tool_tx_idle_chars',
        default_value='3.5',
        description='Tool TX idle chars'
    ))
    declared_arguments.append(DeclareLaunchArgument(
        'tool_device_name',
        default_value='/tmp/ttyUR',
        description='Tool device name'
    ))
    declared_arguments.append(DeclareLaunchArgument(
        'tool_tcp_port',
        default_value='54321',
        description='Tool TCP port'
    ))

    # Communication ports
    declared_arguments.append(DeclareLaunchArgument(
        'reverse_ip',
        default_value='0.0.0.0',
        description='Reverse IP'
    ))
    declared_arguments.append(DeclareLaunchArgument(
        'script_command_port',
        default_value='50004',
        description='Script command port'
    ))
    declared_arguments.append(DeclareLaunchArgument(
        'reverse_port',
        default_value='50001',
        description='Reverse port'
    ))
    declared_arguments.append(DeclareLaunchArgument(
        'script_sender_port',
        default_value='50002',
        description='Script sender port'
    ))
    declared_arguments.append(DeclareLaunchArgument(
        'trajectory_port',
        default_value='50003',
        description='Trajectory port'
    ))

    # Scene options (custom to this launch file)
    declared_arguments.append(DeclareLaunchArgument(
        'include_gripper',
        default_value='true',
        description='Include gripper in description'
    ))
    declared_arguments.append(DeclareLaunchArgument(
        'include_objects',
        default_value='true',
        description='Include pick/place objects in scene'
    ))
    declared_arguments.append(DeclareLaunchArgument(
        'include_table',
        default_value='true',
        description='Include industrial table in scene'
    ))

    return LaunchDescription(
        declared_arguments + [robot_state_publisher_node]
    )
