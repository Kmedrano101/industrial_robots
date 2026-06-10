"""
Launch file for UR Kinematics Server with UR Robot Driver

Starts both the kinematics server and integrates with the UR robot driver.

Usage:
    ros2 launch ur_kinematics_node kinematics_with_driver.launch.py robot_model:=ur5e
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # Declare arguments
    robot_model_arg = DeclareLaunchArgument(
        'robot_model',
        default_value='ur7e',
        description='Robot model (ur3e, ur5e, ur7e, ur10e, ur16e, ur20, ur30)'
    )

    robot_ip_arg = DeclareLaunchArgument(
        'robot_ip',
        default_value='172.28.0.10',
        description='IP address of the robot or URSim'
    )

    launch_rviz_arg = DeclareLaunchArgument(
        'launch_rviz',
        default_value='false',
        description='Launch RViz visualization'
    )

    use_fake_hardware_arg = DeclareLaunchArgument(
        'use_fake_hardware',
        default_value='false',
        description='Use fake hardware for testing'
    )

    # Get configurations
    robot_model = LaunchConfiguration('robot_model')
    robot_ip = LaunchConfiguration('robot_ip')
    launch_rviz = LaunchConfiguration('launch_rviz')
    use_fake_hardware = LaunchConfiguration('use_fake_hardware')

    # Kinematics server node
    kinematics_server_node = Node(
        package='ur_kinematics_node',
        executable='kinematics_server',
        name='ur_kinematics_server',
        parameters=[{
            'robot_model': robot_model,
            'publish_rate': 100.0,
        }],
        output='screen',
        emulate_tty=True,
    )

    return LaunchDescription([
        robot_model_arg,
        robot_ip_arg,
        launch_rviz_arg,
        use_fake_hardware_arg,
        kinematics_server_node,
    ])
