/**
 * @file robot_model.hpp
 * @brief Robot model loading and parameter management
 *
 * Handles loading robot parameters from YAML configuration files
 * and provides factory functions for different UR models.
 */

#ifndef UR_SCREW_KINEMATICS_ROBOT_MODEL_HPP
#define UR_SCREW_KINEMATICS_ROBOT_MODEL_HPP

#include "ur_screw_kinematics/types.hpp"
#include <string>
#include <memory>

namespace ur_kinematics {

/**
 * @brief Robot model class for managing kinematic parameters
 *
 * Encapsulates robot parameters and provides methods for
 * loading from configuration files.
 */
class RobotModel {
public:
    /**
     * @brief Construct robot model from parameters
     */
    explicit RobotModel(const RobotParameters& params);

    /**
     * @brief Load robot model from YAML configuration file
     *
     * @param config_path Path to YAML configuration file
     * @return Shared pointer to RobotModel
     * @throws std::runtime_error if file cannot be loaded
     */
    static std::shared_ptr<RobotModel> fromYAML(const std::string& config_path);

    /**
     * @brief Get robot model by name
     *
     * Returns built-in parameters for known robot models.
     * Supported: "ur3e", "ur5e", "ur10e", "ur16e", "ur20", "ur30"
     *
     * @param model_name Robot model identifier
     * @return Shared pointer to RobotModel
     * @throws std::invalid_argument if model not found
     */
    static std::shared_ptr<RobotModel> fromName(const std::string& model_name);

    /**
     * @brief Get the underlying parameters struct
     */
    const RobotParameters& parameters() const { return params_; }

    /**
     * @brief Get model name
     */
    const std::string& name() const { return params_.model_name; }

    /**
     * @brief Get number of joints
     */
    int numJoints() const { return params_.num_joints; }

    /**
     * @brief Get home configuration matrix M
     */
    const Matrix4d& homeConfig() const { return params_.M_home; }

    /**
     * @brief Get screw axes in space frame
     */
    const std::vector<ScrewAxis>& screwAxesSpace() const {
        return params_.screw_axes_space;
    }

    /**
     * @brief Get screw axes in body frame
     */
    const std::vector<ScrewAxis>& screwAxesBody() const {
        return params_.screw_axes_body;
    }

    /**
     * @brief Get joint limits
     */
    const std::vector<std::pair<double, double>>& jointLimits() const {
        return params_.joint_limits;
    }

    /**
     * @brief Check if configuration is within joint limits
     */
    bool isWithinLimits(const JointConfiguration& q) const;

    /**
     * @brief Print robot parameters (for debugging)
     */
    void printInfo() const;

private:
    RobotParameters params_;

    // Compute derived parameters from DH parameters
    void computeScrewAxes();
    void computeHomeConfig();
};

// ============================================================================
// Factory Functions for Built-in Robot Models
// ============================================================================

/**
 * @brief Create UR3e robot parameters
 */
RobotParameters createUR3eParameters();

/**
 * @brief Create UR5e robot parameters
 */
RobotParameters createUR5eParameters();

/**
 * @brief Create UR10e robot parameters
 */
RobotParameters createUR10eParameters();

/**
 * @brief Create UR16e robot parameters
 */
RobotParameters createUR16eParameters();

/**
 * @brief Create UR20 robot parameters
 */
RobotParameters createUR20Parameters();

/**
 * @brief Create UR30 robot parameters
 */
RobotParameters createUR30Parameters();

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * @brief Compute screw axes from DH parameters
 *
 * Derives screw axis representation from Modified DH parameters.
 *
 * @param a Link lengths
 * @param d Link offsets
 * @param alpha Link twists
 * @return Vector of screw axes in space frame
 */
std::vector<ScrewAxis> dhToScrewAxes(
    const std::vector<double>& a,
    const std::vector<double>& d,
    const std::vector<double>& alpha);

/**
 * @brief Compute home configuration from DH parameters
 *
 * @param a Link lengths
 * @param d Link offsets
 * @param alpha Link twists
 * @return Home configuration matrix M
 */
Matrix4d dhToHomeConfig(
    const std::vector<double>& a,
    const std::vector<double>& d,
    const std::vector<double>& alpha);

/**
 * @brief Get list of supported robot models
 */
std::vector<std::string> getSupportedModels();

/**
 * @brief Check if model name is supported
 */
bool isModelSupported(const std::string& model_name);

}  // namespace ur_kinematics

#endif  // UR_SCREW_KINEMATICS_ROBOT_MODEL_HPP
