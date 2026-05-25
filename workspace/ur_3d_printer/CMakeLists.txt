cmake_minimum_required(VERSION 3.8)
project(ur_3d_printer)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclpy REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(visualization_msgs REQUIRED)
find_package(control_msgs REQUIRED)
find_package(trajectory_msgs REQUIRED)
find_package(action_msgs REQUIRED)

# Generate messages, services, and actions
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/PrintState.msg"
  "msg/PrintProgress.msg"
  "msg/ExtruderState.msg"
  "srv/StartPrint.srv"
  "srv/PausePrint.srv"
  "srv/ResumePrint.srv"
  "srv/CancelPrint.srv"
  "srv/CalibrateOrigin.srv"
  "srv/SetExtruder.srv"
  "action/ExecutePrint.action"
  DEPENDENCIES
    std_msgs
    geometry_msgs
)

# Get Python version for site-packages path
find_package(Python3 REQUIRED COMPONENTS Interpreter)

# Install Python modules
install(DIRECTORY ur_3d_printer/
  DESTINATION lib/python${Python3_VERSION_MAJOR}.${Python3_VERSION_MINOR}/site-packages/${PROJECT_NAME}
  FILES_MATCHING PATTERN "*.py"
)

# Install executable scripts
install(PROGRAMS
  scripts/print_node
  scripts/extruder_controller
  scripts/toolpath_visualizer
  scripts/deposition_visualizer
  scripts/mock_controller
  DESTINATION lib/${PROJECT_NAME}
)

# Install launch files
install(DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

# Install config files
install(DIRECTORY config/
  DESTINATION share/${PROJECT_NAME}/config
)

# Install URDF files
install(DIRECTORY urdf/
  DESTINATION share/${PROJECT_NAME}/urdf
)

# Install resource files (gcode, stl, etc.)
install(DIRECTORY resource/
  DESTINATION share/${PROJECT_NAME}/resource
  PATTERN "ur_3d_printer" EXCLUDE
)

# Install resource marker for ament index
install(FILES resource/${PROJECT_NAME}
  DESTINATION share/ament_index/resource_index/packages
)

install(FILES package.xml
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  # Use custom flake8 config (allows Google-style docstrings and import ordering)
  set(ament_cmake_flake8_CONFIG_FILE "${CMAKE_CURRENT_SOURCE_DIR}/ament_flake8.ini")
  # Exclude pep257 from auto-run; we call it manually with extra ignores
  list(APPEND AMENT_LINT_AUTO_EXCLUDE ament_cmake_pep257)

  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()

  # pep257 with extra ignores for Google-style docstrings
  find_package(ament_cmake_pep257 QUIET)
  if(ament_cmake_pep257_FOUND)
    ament_pep257(--add-ignore D204 D213 D400 D406 D407 D413 D415)
  endif()

  # Unit tests
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_gcode_parser test/test_gcode_parser.py)
  ament_add_pytest_test(test_toolpath test/test_toolpath.py)
  ament_add_pytest_test(test_trajectory_planner test/test_trajectory_planner.py)
  ament_add_pytest_test(test_workspace_validator test/test_workspace_validator.py)
  ament_add_pytest_test(test_collision_checker test/test_collision_checker.py)
  ament_add_pytest_test(test_multiaxis_planner test/test_multiaxis_planner.py)
endif()

ament_package()
