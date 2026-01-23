/**
 * @file ur_screw_kinematics.hpp
 * @brief Main header file - includes all library components
 *
 * Universal Robots Screw Theory Kinematics Library
 *
 * This library provides forward and inverse kinematics for Universal Robots
 * using the Product of Exponentials (PoE) formulation based on screw theory.
 *
 * Features:
 * - Forward kinematics using space and body frame formulations
 * - Analytical inverse kinematics using Paden-Kahan subproblems
 * - Numerical inverse kinematics (Newton-Raphson, Levenberg-Marquardt)
 * - Space and body Jacobian computation
 * - Support for all UR robot models (UR3e, UR5e, UR10e, UR16e, UR20, UR30)
 * - Configuration file support for custom parameters
 *
 * Usage:
 * @code
 * #include <ur_screw_kinematics/ur_screw_kinematics.hpp>
 *
 * using namespace ur_kinematics;
 *
 * // Load robot model
 * auto robot = RobotModel::fromName("ur5e");
 *
 * // Forward kinematics
 * JointConfiguration q;
 * q << 0, -PI/4, PI/2, -PI/4, PI/2, 0;
 * Matrix4d T = fk(robot->parameters(), q);
 *
 * // Inverse kinematics
 * IKSolutions solutions = ik_analytical(robot->parameters(), T);
 * @endcode
 *
 * @author Based on Screw Theory in Robotics by Dr. Jose M. Pardos-Gotor
 * @see https://github.com/DrPardosGotor/Screw-Theory-in-Robotics
 */

#ifndef UR_SCREW_KINEMATICS_HPP
#define UR_SCREW_KINEMATICS_HPP

// Core types and definitions
#include "ur_screw_kinematics/types.hpp"

// Lie algebra operations
#include "ur_screw_kinematics/lie_algebra.hpp"

// Forward kinematics
#include "ur_screw_kinematics/forward_kinematics.hpp"

// Inverse kinematics
#include "ur_screw_kinematics/inverse_kinematics.hpp"

// Jacobian computation
#include "ur_screw_kinematics/jacobian.hpp"

// Robot model and parameters
#include "ur_screw_kinematics/robot_model.hpp"

namespace ur_kinematics {

/**
 * @brief Get library version string
 */
inline const char* version() {
    return "1.0.0";
}

/**
 * @brief Get library description
 */
inline const char* description() {
    return "Universal Robots Screw Theory Kinematics Library";
}

}  // namespace ur_kinematics

#endif  // UR_SCREW_KINEMATICS_HPP
