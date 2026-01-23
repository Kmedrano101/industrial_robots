cmake_minimum_required(VERSION 3.8)
project(ur_screw_kinematics VERSION 1.0.0)

# C++ standard
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

# Compiler options
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Build type
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(Eigen3 REQUIRED)

# Option for Python bindings
option(BUILD_PYTHON_BINDINGS "Build Python bindings using pybind11" ON)

# Core library
add_library(${PROJECT_NAME} SHARED
  src/lie_algebra.cpp
  src/forward_kinematics.cpp
  src/inverse_kinematics.cpp
  src/jacobian.cpp
  src/robot_model.cpp
)

target_include_directories(${PROJECT_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
  ${EIGEN3_INCLUDE_DIRS}
)

target_link_libraries(${PROJECT_NAME}
  Eigen3::Eigen
)

# Set library properties
set_target_properties(${PROJECT_NAME} PROPERTIES
  VERSION ${PROJECT_VERSION}
  SOVERSION 1
)

# Python bindings
if(BUILD_PYTHON_BINDINGS)
  find_package(Python3 COMPONENTS Interpreter Development REQUIRED)
  find_package(pybind11 CONFIG QUIET)

  if(pybind11_FOUND)
    message(STATUS "Building Python bindings with pybind11")

    pybind11_add_module(ur_kinematics_py python/bindings.cpp)
    target_link_libraries(ur_kinematics_py PRIVATE ${PROJECT_NAME})
    target_include_directories(ur_kinematics_py PRIVATE
      ${CMAKE_CURRENT_SOURCE_DIR}/include
      ${EIGEN3_INCLUDE_DIRS}
    )

    # Install Python module
    install(TARGETS ur_kinematics_py
      LIBRARY DESTINATION lib/python${Python3_VERSION_MAJOR}.${Python3_VERSION_MINOR}/site-packages
    )
  else()
    message(WARNING "pybind11 not found, skipping Python bindings")
  endif()
endif()

# Install targets
install(TARGETS ${PROJECT_NAME}
  EXPORT ${PROJECT_NAME}Targets
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

# Install headers
install(DIRECTORY include/
  DESTINATION include
)

# Install config files
install(DIRECTORY config/
  DESTINATION share/${PROJECT_NAME}/config
)

# Export targets
install(EXPORT ${PROJECT_NAME}Targets
  FILE ${PROJECT_NAME}Targets.cmake
  NAMESPACE ${PROJECT_NAME}::
  DESTINATION lib/cmake/${PROJECT_NAME}
)

# Create Config.cmake
include(CMakePackageConfigHelpers)
configure_package_config_file(
  ${CMAKE_CURRENT_SOURCE_DIR}/cmake/Config.cmake.in
  ${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_NAME}Config.cmake
  INSTALL_DESTINATION lib/cmake/${PROJECT_NAME}
)

write_basic_package_version_file(
  ${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_NAME}ConfigVersion.cmake
  VERSION ${PROJECT_VERSION}
  COMPATIBILITY SameMajorVersion
)

install(FILES
  ${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_NAME}Config.cmake
  ${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_NAME}ConfigVersion.cmake
  DESTINATION lib/cmake/${PROJECT_NAME}
)

# Testing
if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()

  # Add unit tests
  find_package(ament_cmake_gtest REQUIRED)

  ament_add_gtest(test_lie_algebra test/test_lie_algebra.cpp)
  target_link_libraries(test_lie_algebra ${PROJECT_NAME})

  ament_add_gtest(test_forward_kinematics test/test_forward_kinematics.cpp)
  target_link_libraries(test_forward_kinematics ${PROJECT_NAME})

  ament_add_gtest(test_inverse_kinematics test/test_inverse_kinematics.cpp)
  target_link_libraries(test_inverse_kinematics ${PROJECT_NAME})
endif()

ament_export_include_directories(include)
ament_export_libraries(${PROJECT_NAME})
ament_export_targets(${PROJECT_NAME}Targets)
ament_export_dependencies(Eigen3)

ament_package()
