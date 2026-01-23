cmake_minimum_required(VERSION 3.8)
project(ur_kinematics_msgs)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  # Messages
  "msg/JointConfiguration.msg"
  "msg/KinematicState.msg"
  "msg/IKSolution.msg"
  "msg/Jacobian.msg"
  # Services
  "srv/ComputeFK.srv"
  "srv/ComputeIK.srv"
  "srv/ComputeJacobian.srv"
  "srv/GetRobotInfo.srv"
  DEPENDENCIES
    std_msgs
    geometry_msgs
    sensor_msgs
)

ament_export_dependencies(rosidl_default_runtime)

ament_package()
