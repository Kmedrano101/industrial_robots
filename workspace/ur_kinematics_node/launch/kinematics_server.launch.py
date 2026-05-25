"""
Launch file for UR Kinematics Server

Starts the kinematics server node with configurable robot model.

Usage:
    ros2 launch ur_kinematics_node kinematics_server.launch.py
    ros2 launch ur_kinematics_node kinematics_server.launch.py robot_model:=ur10e
    ros2 launch ur_kinematics_node kinematics_server.launch.py config_file:=/path/to/custom.yaml
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # Declare arguments
    robot_model_arg = DeclareLaunchArgument(
        'robot_model',
        default_value='ur5e',
        description='Robot model (ur3e, ur5e, ur10e, ur16e, ur20, ur30)',
        choices=['ur3e', 'ur5e', 'ur10e', 'ur16e', 'ur20', 'ur30']
    )

    config_file_arg = DeclareLaunchArgument(
        'config_file',
        default_value='',
        description='Path to custom robot configuration YAML file (overrides robot_model)'
    )

    publish_rate_arg = DeclareLaunchArgument(
        'publish_rate',
        default_value='100.0',
        description='Rate for kinematic state publishing (Hz)'
    )

    namespace_arg = DeclareLaunchArgument(
        'namespace',
        default_value='',
        description='Namespace for the node'
    )

    # Get configuration
    robot_model = LaunchConfiguration('robot_model')
    config_file = LaunchConfiguration('config_file')
    publish_rate = LaunchConfiguration('publish_rate')
    namespace = LaunchConfiguration('namespace')

    # Kinematics server node
    kinematics_server_node = Node(
        package='ur_kinematics_node',
        executable='kinematics_server',
        name='ur_kinematics_server',
        namespace=namespace,
        parameters=[{
            'robot_model': robot_model,
            'config_file': config_file,
            'publish_rate': publish_rate,
        }],
        output='screen',
        emulate_tty=True,
    )

    return LaunchDescription([
        robot_model_arg,
        config_file_arg,
        publish_rate_arg,
        namespace_arg,
        kinematics_server_node,
    ])
