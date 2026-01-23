/**
 * @file bindings.cpp
 * @brief Python bindings for ur_screw_kinematics library using pybind11
 */

#include <pybind11/pybind11.h>
#include <pybind11/eigen.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>

#include "ur_screw_kinematics/ur_screw_kinematics.hpp"

namespace py = pybind11;
using namespace ur_kinematics;

PYBIND11_MODULE(ur_kinematics_py, m) {
    m.doc() = R"doc(
        UR Screw Kinematics Python Bindings

        This module provides Python bindings for the ur_screw_kinematics C++ library,
        implementing forward and inverse kinematics for Universal Robots using
        screw theory (Product of Exponentials formulation).

        Example:
            >>> import ur_kinematics_py as urk
            >>> robot = urk.RobotModel.from_name("ur5e")
            >>> joints = [0, -1.57, 1.57, 0, 1.57, 0]
            >>> pose = urk.fk(robot.parameters(), joints)
            >>> print(pose)
    )doc";

    // Version info
    m.attr("__version__") = ur_kinematics::version();

    // Constants
    m.attr("PI") = PI;
    m.attr("EPSILON") = EPSILON;

    // ========================================================================
    // Transform class
    // ========================================================================
    py::class_<Transform>(m, "Transform", "SE(3) transformation matrix wrapper")
        .def(py::init<>())
        .def(py::init<const Matrix4d&>())
        .def_readwrite("matrix", &Transform::matrix)
        .def("rotation", &Transform::rotation)
        .def("translation", &Transform::translation)
        .def("inverse", &Transform::inverse)
        .def("__mul__", &Transform::operator*)
        .def("__repr__", [](const Transform& t) {
            std::ostringstream oss;
            oss << "Transform(\n" << t.matrix << "\n)";
            return oss.str();
        });

    // ========================================================================
    // IKSolution class
    // ========================================================================
    py::class_<IKSolution>(m, "IKSolution", "Inverse kinematics solution")
        .def(py::init<>())
        .def_readwrite("joints", &IKSolution::joints)
        .def_readwrite("is_valid", &IKSolution::is_valid)
        .def_readwrite("error", &IKSolution::error)
        .def_readwrite("iterations", &IKSolution::iterations)
        .def_readwrite("method", &IKSolution::method)
        .def("__repr__", [](const IKSolution& sol) {
            std::ostringstream oss;
            oss << "IKSolution(valid=" << sol.is_valid
                << ", error=" << sol.error
                << ", joints=[" << sol.joints.transpose() << "])";
            return oss.str();
        });

    // ========================================================================
    // IKSolutions class
    // ========================================================================
    py::class_<IKSolutions>(m, "IKSolutions", "Collection of IK solutions")
        .def(py::init<>())
        .def_readwrite("solutions", &IKSolutions::solutions)
        .def("valid_count", &IKSolutions::validCount)
        .def("nearest_to", &IKSolutions::nearestTo)
        .def("__len__", [](const IKSolutions& s) { return s.solutions.size(); })
        .def("__getitem__", [](const IKSolutions& s, size_t i) {
            if (i >= s.solutions.size()) throw py::index_error();
            return s.solutions[i];
        });

    // ========================================================================
    // FKResult class
    // ========================================================================
    py::class_<FKResult>(m, "FKResult", "Forward kinematics result with joint transforms")
        .def(py::init<>())
        .def_readwrite("end_effector_pose", &FKResult::end_effector_pose)
        .def_readwrite("joint_transforms", &FKResult::joint_transforms)
        .def_readwrite("is_valid", &FKResult::is_valid);

    // ========================================================================
    // RobotParameters struct
    // ========================================================================
    py::class_<RobotParameters>(m, "RobotParameters", "Robot kinematic parameters")
        .def(py::init<>())
        .def_readwrite("model_name", &RobotParameters::model_name)
        .def_readwrite("num_joints", &RobotParameters::num_joints)
        .def_readwrite("a", &RobotParameters::a)
        .def_readwrite("d", &RobotParameters::d)
        .def_readwrite("alpha", &RobotParameters::alpha)
        .def_readwrite("M_home", &RobotParameters::M_home)
        .def_readwrite("screw_axes_space", &RobotParameters::screw_axes_space)
        .def_readwrite("screw_axes_body", &RobotParameters::screw_axes_body)
        .def_readwrite("joint_limits", &RobotParameters::joint_limits);

    // ========================================================================
    // RobotModel class
    // ========================================================================
    py::class_<RobotModel, std::shared_ptr<RobotModel>>(m, "RobotModel",
        "Robot model for managing kinematic parameters")
        .def(py::init<const RobotParameters&>())
        .def_static("from_name", &RobotModel::fromName,
            py::arg("model_name"),
            "Load built-in robot model by name (ur3e, ur5e, ur10e, ur16e, ur20, ur30)")
        .def_static("from_yaml", &RobotModel::fromYAML,
            py::arg("config_path"),
            "Load robot model from YAML configuration file")
        .def("parameters", &RobotModel::parameters,
            py::return_value_policy::reference_internal)
        .def("name", &RobotModel::name)
        .def("num_joints", &RobotModel::numJoints)
        .def("home_config", &RobotModel::homeConfig)
        .def("screw_axes_space", &RobotModel::screwAxesSpace)
        .def("screw_axes_body", &RobotModel::screwAxesBody)
        .def("joint_limits", &RobotModel::jointLimits)
        .def("is_within_limits", &RobotModel::isWithinLimits)
        .def("print_info", &RobotModel::printInfo);

    // ========================================================================
    // Lie algebra functions
    // ========================================================================
    auto lie_module = m.def_submodule("lie", "Lie algebra operations");

    lie_module.def("skew3", &lie::skew3, py::arg("v"),
        "Create 3x3 skew-symmetric matrix from 3-vector");
    lie_module.def("unskew3", &lie::unskew3, py::arg("m"),
        "Extract 3-vector from skew-symmetric matrix");
    lie_module.def("rodrigues", &lie::rodrigues,
        py::arg("omega_hat"), py::arg("theta"),
        "Rodrigues formula for rotation matrix");
    lie_module.def("exp_so3", &lie::exp_so3, py::arg("omega"),
        "Matrix exponential so(3) -> SO(3)");
    lie_module.def("log_so3", &lie::log_so3, py::arg("R"),
        "Matrix logarithm SO(3) -> so(3)");
    lie_module.def("exp_screw", &lie::exp_screw,
        py::arg("screw_axis"), py::arg("theta"),
        "Matrix exponential se(3) -> SE(3) for screw motion");
    lie_module.def("log_se3", &lie::log_se3, py::arg("T"),
        "Matrix logarithm SE(3) -> se(3)");
    lie_module.def("adjoint", py::overload_cast<const Matrix4d&>(&lie::adjoint),
        py::arg("T"),
        "6x6 adjoint representation of SE(3)");
    lie_module.def("adjoint_inverse", &lie::adjoint_inverse, py::arg("T"),
        "Inverse adjoint representation");
    lie_module.def("rotx", &lie::rotx, py::arg("theta"),
        "Rotation matrix about X axis");
    lie_module.def("roty", &lie::roty, py::arg("theta"),
        "Rotation matrix about Y axis");
    lie_module.def("rotz", &lie::rotz, py::arg("theta"),
        "Rotation matrix about Z axis");

    // ========================================================================
    // Forward kinematics functions
    // ========================================================================
    m.def("fk_space_frame", &fk_space_frame,
        py::arg("screw_axes"), py::arg("M_home"), py::arg("joint_angles"),
        "Forward kinematics using space frame PoE formulation");

    m.def("fk_body_frame", &fk_body_frame,
        py::arg("screw_axes"), py::arg("M_home"), py::arg("joint_angles"),
        "Forward kinematics using body frame PoE formulation");

    m.def("fk", &fk,
        py::arg("params"), py::arg("joint_angles"), py::arg("use_space_frame") = true,
        "Forward kinematics using robot parameters");

    m.def("fk_position", &fk_position,
        py::arg("params"), py::arg("joint_angles"),
        "Compute end-effector position only");

    m.def("fk_orientation", &fk_orientation,
        py::arg("params"), py::arg("joint_angles"),
        "Compute end-effector orientation only");

    m.def("fk_with_joint_transforms", &fk_with_joint_transforms,
        py::arg("screw_axes"), py::arg("M_home"), py::arg("joint_angles"),
        "Forward kinematics with intermediate joint transforms");

    // ========================================================================
    // Inverse kinematics functions
    // ========================================================================
    m.def("ik_analytical", &ik_analytical,
        py::arg("params"), py::arg("T_target"),
        "Analytical IK for UR robots (returns up to 8 solutions)");

    m.def("ik_newton_raphson", &ik_newton_raphson,
        py::arg("params"), py::arg("T_target"), py::arg("theta_init"),
        py::arg("tolerance") = IK_TOLERANCE, py::arg("max_iterations") = MAX_IK_ITERATIONS,
        "Numerical IK using Newton-Raphson iteration");

    m.def("ik_levenberg_marquardt", &ik_levenberg_marquardt,
        py::arg("params"), py::arg("T_target"), py::arg("theta_init"),
        py::arg("tolerance") = IK_TOLERANCE, py::arg("max_iterations") = MAX_IK_ITERATIONS,
        "Numerical IK using Levenberg-Marquardt algorithm");

    m.def("ik_with_limits", &ik_with_limits,
        py::arg("params"), py::arg("T_target"),
        py::arg("method") = "analytical",
        py::arg("theta_init") = JointConfiguration::Zero(),
        "IK with joint limit enforcement");

    m.def("ik_position_only", &ik_position_only,
        py::arg("params"), py::arg("target_position"),
        py::arg("theta_init") = JointConfiguration::Zero(),
        "Position-only IK (orientation unconstrained)");

    m.def("pose_error", &pose_error,
        py::arg("T_current"), py::arg("T_target"),
        "Compute twist error between two poses");

    m.def("normalize_angles", &normalize_angles, py::arg("theta"),
        "Normalize joint angles to [-pi, pi]");

    m.def("check_joint_limits", &check_joint_limits,
        py::arg("theta"), py::arg("limits"),
        "Check if configuration respects joint limits");

    // ========================================================================
    // Jacobian functions
    // ========================================================================
    m.def("jacobian_space", &jacobian_space,
        py::arg("screw_axes_space"), py::arg("joint_angles"),
        "Compute space Jacobian");

    m.def("jacobian_body", &jacobian_body,
        py::arg("screw_axes_body"), py::arg("joint_angles"),
        "Compute body Jacobian");

    m.def("jacobian", &jacobian,
        py::arg("params"), py::arg("joint_angles"), py::arg("use_space_frame") = true,
        "Compute Jacobian using robot parameters");

    m.def("manipulability", &manipulability, py::arg("J"),
        "Compute manipulability measure");

    m.def("condition_number", &condition_number, py::arg("J"),
        "Compute Jacobian condition number");

    m.def("is_near_singularity", &is_near_singularity,
        py::arg("J"), py::arg("threshold") = 1e-3,
        "Check if near singularity");

    m.def("jacobian_pseudoinverse", &jacobian_pseudoinverse,
        py::arg("J"), py::arg("damping") = 0.0,
        "Compute Jacobian pseudoinverse");

    m.def("jacobian_damped_inverse", &jacobian_damped_inverse,
        py::arg("J"), py::arg("lambda") = 0.01,
        "Compute damped least-squares inverse");

    // ========================================================================
    // Utility functions
    // ========================================================================
    m.def("get_supported_models", &getSupportedModels,
        "Get list of supported robot model names");

    m.def("is_model_supported", &isModelSupported, py::arg("model_name"),
        "Check if robot model is supported");
}
