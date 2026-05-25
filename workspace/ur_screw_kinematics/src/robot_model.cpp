/**
 * @file robot_model.cpp
 * @brief Implementation of robot model loading and built-in parameters
 */

#include "ur_screw_kinematics/robot_model.hpp"
#include "ur_screw_kinematics/forward_kinematics.hpp"
#include "ur_screw_kinematics/inverse_kinematics.hpp"
#include "ur_screw_kinematics/lie_algebra.hpp"
#include <iostream>
#include <fstream>
#include <stdexcept>
#include <algorithm>
#include <cmath>

namespace ur_kinematics {

// ============================================================================
// RobotModel Class Implementation
// ============================================================================

RobotModel::RobotModel(const RobotParameters& params) : params_(params) {
    // Compute body frame screw axes if not provided
    if (params_.screw_axes_body.empty() && !params_.screw_axes_space.empty()) {
        params_.screw_axes_body = space_to_body_screws(
            params_.screw_axes_space, params_.M_home);
    }
}

std::shared_ptr<RobotModel> RobotModel::fromName(const std::string& model_name) {
    std::string name_lower = model_name;
    std::transform(name_lower.begin(), name_lower.end(), name_lower.begin(), ::tolower);

    RobotParameters params;

    if (name_lower == "ur3e") {
        params = createUR3eParameters();
    } else if (name_lower == "ur5e") {
        params = createUR5eParameters();
    } else if (name_lower == "ur10e") {
        params = createUR10eParameters();
    } else if (name_lower == "ur16e") {
        params = createUR16eParameters();
    } else if (name_lower == "ur20") {
        params = createUR20Parameters();
    } else if (name_lower == "ur30") {
        params = createUR30Parameters();
    } else {
        throw std::invalid_argument("Unknown robot model: " + model_name);
    }

    return std::make_shared<RobotModel>(params);
}

std::shared_ptr<RobotModel> RobotModel::fromYAML(const std::string& config_path) {
    // Simple YAML-like parsing (for a proper implementation, use yaml-cpp)
    std::ifstream file(config_path);
    if (!file.is_open()) {
        throw std::runtime_error("Cannot open config file: " + config_path);
    }

    RobotParameters params;
    params.num_joints = 6;

    std::string line;
    std::string current_section;

    while (std::getline(file, line)) {
        // Skip comments and empty lines
        if (line.empty() || line[0] == '#') continue;

        // Check for section
        if (line.find("model_name:") != std::string::npos) {
            size_t pos = line.find(':');
            params.model_name = line.substr(pos + 1);
            // Trim whitespace
            params.model_name.erase(0, params.model_name.find_first_not_of(" \t"));
            params.model_name.erase(params.model_name.find_last_not_of(" \t") + 1);
        }
        // Add more YAML parsing as needed...
    }

    // If model name matches a built-in, use those parameters
    if (!params.model_name.empty() && isModelSupported(params.model_name)) {
        return fromName(params.model_name);
    }

    return std::make_shared<RobotModel>(params);
}

bool RobotModel::isWithinLimits(const JointConfiguration& q) const {
    return check_joint_limits(q, params_.joint_limits);
}

void RobotModel::printInfo() const {
    std::cout << "Robot Model: " << params_.model_name << std::endl;
    std::cout << "Number of joints: " << params_.num_joints << std::endl;

    std::cout << "\nDH Parameters (a, d, alpha):" << std::endl;
    for (int i = 0; i < params_.num_joints; ++i) {
        std::cout << "  Joint " << (i + 1) << ": "
                  << params_.a[i] << ", "
                  << params_.d[i] << ", "
                  << params_.alpha[i] << std::endl;
    }

    std::cout << "\nHome Configuration M:" << std::endl;
    std::cout << params_.M_home << std::endl;

    std::cout << "\nSpace Frame Screw Axes:" << std::endl;
    for (size_t i = 0; i < params_.screw_axes_space.size(); ++i) {
        std::cout << "  S" << (i + 1) << ": "
                  << params_.screw_axes_space[i].transpose() << std::endl;
    }
}

// ============================================================================
// Built-in Robot Parameters
// ============================================================================

RobotParameters createUR5eParameters() {
    RobotParameters params;
    params.model_name = "ur5e";
    params.num_joints = 6;

    // DH Parameters (Modified DH Convention) from Universal Robots
    // a: link length (x-axis)
    // d: link offset (z-axis)
    // alpha: link twist (rotation about x-axis)
    params.a = {0.0, -0.425, -0.3922, 0.0, 0.0, 0.0};
    params.d = {0.1625, 0.0, 0.0, 0.1333, 0.0997, 0.0996};
    params.alpha = {PI / 2, 0.0, 0.0, PI / 2, -PI / 2, 0.0};

    // Derived link parameters for screw theory
    double L1 = 0.425;    // Upper arm length |a2|
    double L2 = 0.3922;   // Forearm length |a3|
    double W1 = 0.1333;   // Wrist 1 offset (d4)
    double W2 = 0.0997;   // Wrist 2 offset (d5)
    double H1 = 0.1625;   // Shoulder height (d1)
    double H2 = 0.0996;   // Tool offset (d6)

    params.link_lengths = {L1, L2};
    params.offsets = {W1, W2, H1, H2};

    // Home configuration M (end-effector pose at zero joint angles)
    // For UR5e at home position, the end-effector is at:
    params.M_home = Matrix4d::Identity();
    params.M_home(0, 0) = -1;  // Rotation
    params.M_home(1, 1) = -1;
    params.M_home(0, 3) = L1 + L2;  // X position
    params.M_home(1, 3) = W1 + W2;  // Y position
    params.M_home(2, 3) = H1 - H2;  // Z position

    // Screw axes in space frame at home configuration
    // S = [omega; v] where v = -omega x q (q is point on axis)
    params.screw_axes_space.resize(6);

    // Joint 1: Rotation about Z at origin
    params.screw_axes_space[0] << 0, 0, 1, 0, 0, 0;

    // Joint 2: Rotation about Y at (0, 0, H1)
    params.screw_axes_space[1] << 0, 1, 0, -H1, 0, 0;

    // Joint 3: Rotation about Y at (L1, 0, H1)
    params.screw_axes_space[2] << 0, 1, 0, -H1, 0, L1;

    // Joint 4: Rotation about Y at (L1+L2, 0, H1)
    params.screw_axes_space[3] << 0, 1, 0, -H1, 0, L1 + L2;

    // Joint 5: Rotation about Z at (L1+L2, W1, H1)
    params.screw_axes_space[4] << 0, 0, -1, -W1, L1 + L2, 0;

    // Joint 6: Rotation about Y at (L1+L2, W1+W2, H1)
    params.screw_axes_space[5] << 0, 1, 0, -(H1), 0, L1 + L2;

    // Compute body frame screw axes
    params.screw_axes_body = space_to_body_screws(
        params.screw_axes_space, params.M_home);

    // Joint limits (radians) - typical UR5e limits
    params.joint_limits = {
        {-2 * PI, 2 * PI},  // Joint 1
        {-2 * PI, 2 * PI},  // Joint 2
        {-2 * PI, 2 * PI},  // Joint 3
        {-2 * PI, 2 * PI},  // Joint 4
        {-2 * PI, 2 * PI},  // Joint 5
        {-2 * PI, 2 * PI}   // Joint 6
    };

    // Dynamic parameters
    params.link_masses = {3.761, 8.058, 2.846, 1.37, 1.3, 0.365};
    params.link_com = {
        Vector3d(0, -0.02561, 0.00193),
        Vector3d(0.2125, 0, 0.11336),
        Vector3d(0.15, 0.0, 0.0265),
        Vector3d(0, -0.0018, 0.01634),
        Vector3d(0, 0.0018, 0.01634),
        Vector3d(0, 0, -0.001159)
    };

    return params;
}

RobotParameters createUR3eParameters() {
    RobotParameters params;
    params.model_name = "ur3e";
    params.num_joints = 6;

    // DH Parameters for UR3e
    params.a = {0.0, -0.24355, -0.2132, 0.0, 0.0, 0.0};
    params.d = {0.15185, 0.0, 0.0, 0.13105, 0.08535, 0.0921};
    params.alpha = {PI / 2, 0.0, 0.0, PI / 2, -PI / 2, 0.0};

    double L1 = 0.24355;
    double L2 = 0.2132;
    double W1 = 0.13105;
    double W2 = 0.08535;
    double H1 = 0.15185;
    double H2 = 0.0921;

    params.link_lengths = {L1, L2};
    params.offsets = {W1, W2, H1, H2};

    params.M_home = Matrix4d::Identity();
    params.M_home(0, 0) = -1;
    params.M_home(1, 1) = -1;
    params.M_home(0, 3) = L1 + L2;
    params.M_home(1, 3) = W1 + W2;
    params.M_home(2, 3) = H1 - H2;

    params.screw_axes_space.resize(6);
    params.screw_axes_space[0] << 0, 0, 1, 0, 0, 0;
    params.screw_axes_space[1] << 0, 1, 0, -H1, 0, 0;
    params.screw_axes_space[2] << 0, 1, 0, -H1, 0, L1;
    params.screw_axes_space[3] << 0, 1, 0, -H1, 0, L1 + L2;
    params.screw_axes_space[4] << 0, 0, -1, -W1, L1 + L2, 0;
    params.screw_axes_space[5] << 0, 1, 0, -H1, 0, L1 + L2;

    params.screw_axes_body = space_to_body_screws(
        params.screw_axes_space, params.M_home);

    params.joint_limits = {
        {-2 * PI, 2 * PI}, {-2 * PI, 2 * PI}, {-2 * PI, 2 * PI},
        {-2 * PI, 2 * PI}, {-2 * PI, 2 * PI}, {-2 * PI, 2 * PI}
    };

    return params;
}

RobotParameters createUR10eParameters() {
    RobotParameters params;
    params.model_name = "ur10e";
    params.num_joints = 6;

    // DH Parameters for UR10e
    params.a = {0.0, -0.6127, -0.57155, 0.0, 0.0, 0.0};
    params.d = {0.1807, 0.0, 0.0, 0.17415, 0.11985, 0.11655};
    params.alpha = {PI / 2, 0.0, 0.0, PI / 2, -PI / 2, 0.0};

    double L1 = 0.6127;
    double L2 = 0.57155;
    double W1 = 0.17415;
    double W2 = 0.11985;
    double H1 = 0.1807;
    double H2 = 0.11655;

    params.link_lengths = {L1, L2};
    params.offsets = {W1, W2, H1, H2};

    params.M_home = Matrix4d::Identity();
    params.M_home(0, 0) = -1;
    params.M_home(1, 1) = -1;
    params.M_home(0, 3) = L1 + L2;
    params.M_home(1, 3) = W1 + W2;
    params.M_home(2, 3) = H1 - H2;

    params.screw_axes_space.resize(6);
    params.screw_axes_space[0] << 0, 0, 1, 0, 0, 0;
    params.screw_axes_space[1] << 0, 1, 0, -H1, 0, 0;
    params.screw_axes_space[2] << 0, 1, 0, -H1, 0, L1;
    params.screw_axes_space[3] << 0, 1, 0, -H1, 0, L1 + L2;
    params.screw_axes_space[4] << 0, 0, -1, -W1, L1 + L2, 0;
    params.screw_axes_space[5] << 0, 1, 0, -H1, 0, L1 + L2;

    params.screw_axes_body = space_to_body_screws(
        params.screw_axes_space, params.M_home);

    params.joint_limits = {
        {-2 * PI, 2 * PI}, {-2 * PI, 2 * PI}, {-2 * PI, 2 * PI},
        {-2 * PI, 2 * PI}, {-2 * PI, 2 * PI}, {-2 * PI, 2 * PI}
    };

    return params;
}

RobotParameters createUR16eParameters() {
    RobotParameters params;
    params.model_name = "ur16e";
    params.num_joints = 6;

    // DH Parameters for UR16e
    params.a = {0.0, -0.4784, -0.36, 0.0, 0.0, 0.0};
    params.d = {0.1807, 0.0, 0.0, 0.17415, 0.11985, 0.11655};
    params.alpha = {PI / 2, 0.0, 0.0, PI / 2, -PI / 2, 0.0};

    double L1 = 0.4784;
    double L2 = 0.36;
    double W1 = 0.17415;
    double W2 = 0.11985;
    double H1 = 0.1807;
    double H2 = 0.11655;

    params.link_lengths = {L1, L2};
    params.offsets = {W1, W2, H1, H2};

    params.M_home = Matrix4d::Identity();
    params.M_home(0, 0) = -1;
    params.M_home(1, 1) = -1;
    params.M_home(0, 3) = L1 + L2;
    params.M_home(1, 3) = W1 + W2;
    params.M_home(2, 3) = H1 - H2;

    params.screw_axes_space.resize(6);
    params.screw_axes_space[0] << 0, 0, 1, 0, 0, 0;
    params.screw_axes_space[1] << 0, 1, 0, -H1, 0, 0;
    params.screw_axes_space[2] << 0, 1, 0, -H1, 0, L1;
    params.screw_axes_space[3] << 0, 1, 0, -H1, 0, L1 + L2;
    params.screw_axes_space[4] << 0, 0, -1, -W1, L1 + L2, 0;
    params.screw_axes_space[5] << 0, 1, 0, -H1, 0, L1 + L2;

    params.screw_axes_body = space_to_body_screws(
        params.screw_axes_space, params.M_home);

    params.joint_limits = {
        {-2 * PI, 2 * PI}, {-2 * PI, 2 * PI}, {-2 * PI, 2 * PI},
        {-2 * PI, 2 * PI}, {-2 * PI, 2 * PI}, {-2 * PI, 2 * PI}
    };

    return params;
}

RobotParameters createUR20Parameters() {
    RobotParameters params;
    params.model_name = "ur20";
    params.num_joints = 6;

    // DH Parameters for UR20 (approximate - verify with official specs)
    params.a = {0.0, -0.8620, -0.7287, 0.0, 0.0, 0.0};
    params.d = {0.2363, 0.0, 0.0, 0.1785, 0.1785, 0.1157};
    params.alpha = {PI / 2, 0.0, 0.0, PI / 2, -PI / 2, 0.0};

    double L1 = 0.8620;
    double L2 = 0.7287;
    double W1 = 0.1785;
    double W2 = 0.1785;
    double H1 = 0.2363;
    double H2 = 0.1157;

    params.link_lengths = {L1, L2};
    params.offsets = {W1, W2, H1, H2};

    params.M_home = Matrix4d::Identity();
    params.M_home(0, 0) = -1;
    params.M_home(1, 1) = -1;
    params.M_home(0, 3) = L1 + L2;
    params.M_home(1, 3) = W1 + W2;
    params.M_home(2, 3) = H1 - H2;

    params.screw_axes_space.resize(6);
    params.screw_axes_space[0] << 0, 0, 1, 0, 0, 0;
    params.screw_axes_space[1] << 0, 1, 0, -H1, 0, 0;
    params.screw_axes_space[2] << 0, 1, 0, -H1, 0, L1;
    params.screw_axes_space[3] << 0, 1, 0, -H1, 0, L1 + L2;
    params.screw_axes_space[4] << 0, 0, -1, -W1, L1 + L2, 0;
    params.screw_axes_space[5] << 0, 1, 0, -H1, 0, L1 + L2;

    params.screw_axes_body = space_to_body_screws(
        params.screw_axes_space, params.M_home);

    params.joint_limits = {
        {-2 * PI, 2 * PI}, {-2 * PI, 2 * PI}, {-2 * PI, 2 * PI},
        {-2 * PI, 2 * PI}, {-2 * PI, 2 * PI}, {-2 * PI, 2 * PI}
    };

    return params;
}

RobotParameters createUR30Parameters() {
    RobotParameters params;
    params.model_name = "ur30";
    params.num_joints = 6;

    // DH Parameters for UR30 (approximate - verify with official specs)
    params.a = {0.0, -0.8620, -0.7287, 0.0, 0.0, 0.0};
    params.d = {0.2363, 0.0, 0.0, 0.1785, 0.1785, 0.1157};
    params.alpha = {PI / 2, 0.0, 0.0, PI / 2, -PI / 2, 0.0};

    double L1 = 0.8620;
    double L2 = 0.7287;
    double W1 = 0.1785;
    double W2 = 0.1785;
    double H1 = 0.2363;
    double H2 = 0.1157;

    params.link_lengths = {L1, L2};
    params.offsets = {W1, W2, H1, H2};

    params.M_home = Matrix4d::Identity();
    params.M_home(0, 0) = -1;
    params.M_home(1, 1) = -1;
    params.M_home(0, 3) = L1 + L2;
    params.M_home(1, 3) = W1 + W2;
    params.M_home(2, 3) = H1 - H2;

    params.screw_axes_space.resize(6);
    params.screw_axes_space[0] << 0, 0, 1, 0, 0, 0;
    params.screw_axes_space[1] << 0, 1, 0, -H1, 0, 0;
    params.screw_axes_space[2] << 0, 1, 0, -H1, 0, L1;
    params.screw_axes_space[3] << 0, 1, 0, -H1, 0, L1 + L2;
    params.screw_axes_space[4] << 0, 0, -1, -W1, L1 + L2, 0;
    params.screw_axes_space[5] << 0, 1, 0, -H1, 0, L1 + L2;

    params.screw_axes_body = space_to_body_screws(
        params.screw_axes_space, params.M_home);

    params.joint_limits = {
        {-2 * PI, 2 * PI}, {-2 * PI, 2 * PI}, {-2 * PI, 2 * PI},
        {-2 * PI, 2 * PI}, {-2 * PI, 2 * PI}, {-2 * PI, 2 * PI}
    };

    return params;
}

// ============================================================================
// Utility Functions
// ============================================================================

std::vector<ScrewAxis> dhToScrewAxes(
    const std::vector<double>& /* a */,
    const std::vector<double>& /* d */,
    const std::vector<double>& /* alpha */) {

    // This is a simplified conversion - proper implementation
    // would compute joint axes and points from DH chain
    std::vector<ScrewAxis> screws;
    // Implementation depends on specific DH convention used
    return screws;
}

Matrix4d dhToHomeConfig(
    const std::vector<double>& /* a */,
    const std::vector<double>& /* d */,
    const std::vector<double>& /* alpha */) {

    // Compute FK at zero configuration using DH
    Matrix4d T = Matrix4d::Identity();
    // Implementation depends on specific DH convention used
    return T;
}

std::vector<std::string> getSupportedModels() {
    return {"ur3e", "ur5e", "ur10e", "ur16e", "ur20", "ur30"};
}

bool isModelSupported(const std::string& model_name) {
    std::string name_lower = model_name;
    std::transform(name_lower.begin(), name_lower.end(), name_lower.begin(), ::tolower);

    auto models = getSupportedModels();
    return std::find(models.begin(), models.end(), name_lower) != models.end();
}

}  // namespace ur_kinematics
