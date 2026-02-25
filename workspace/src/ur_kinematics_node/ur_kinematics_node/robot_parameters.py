"""
Robot Parameters Module

Provides robot kinematic parameters for Universal Robots models.
Supports loading from built-in configurations or YAML files.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
import yaml


@dataclass
class RobotParameters:
    """
    Kinematic parameters for a Universal Robot.

    Attributes:
        model_name: Robot model identifier (e.g., 'ur5e')
        num_joints: Number of joints (6 for UR robots)
        a: DH parameter - link lengths (meters)
        d: DH parameter - link offsets (meters)
        alpha: DH parameter - link twists (radians)
        M_home: Home configuration matrix (4x4)
        screw_axes_space: Screw axes in space frame (6x6)
        screw_axes_body: Screw axes in body frame (6x6)
        joint_limits: Joint limits [(min, max), ...] in radians
    """
    model_name: str = "ur5e"
    num_joints: int = 6

    # DH Parameters
    a: np.ndarray = field(default_factory=lambda: np.zeros(6))
    d: np.ndarray = field(default_factory=lambda: np.zeros(6))
    alpha: np.ndarray = field(default_factory=lambda: np.zeros(6))

    # Derived parameters
    link_lengths: Dict[str, float] = field(default_factory=dict)

    # Screw theory parameters
    M_home: np.ndarray = field(default_factory=lambda: np.eye(4))
    screw_axes_space: np.ndarray = field(default_factory=lambda: np.zeros((6, 6)))
    screw_axes_body: np.ndarray = field(default_factory=lambda: np.zeros((6, 6)))

    # Joint limits
    joint_limits: List[Tuple[float, float]] = field(
        default_factory=lambda: [(-2*np.pi, 2*np.pi)] * 6
    )

    # Dynamic parameters (optional)
    link_masses: Optional[np.ndarray] = None
    link_com: Optional[List[np.ndarray]] = None


def create_ur5e_parameters() -> RobotParameters:
    """Create parameters for UR5e robot."""
    params = RobotParameters()
    params.model_name = "ur5e"
    params.num_joints = 6

    # DH Parameters (Modified DH Convention)
    params.a = np.array([0.0, -0.425, -0.3922, 0.0, 0.0, 0.0])
    params.d = np.array([0.1625, 0.0, 0.0, 0.1333, 0.0997, 0.0996])
    params.alpha = np.array([np.pi/2, 0.0, 0.0, np.pi/2, -np.pi/2, 0.0])

    # Derived link parameters
    L1 = 0.425      # Upper arm length
    L2 = 0.3922     # Forearm length
    W1 = 0.1333     # Wrist 1 offset
    W2 = 0.0997     # Wrist 2 offset
    H1 = 0.1625     # Shoulder height
    H2 = 0.0996     # Tool offset

    params.link_lengths = {'L1': L1, 'L2': L2, 'W1': W1, 'W2': W2, 'H1': H1, 'H2': H2}

    # Home configuration matrix (tool0 at zero config in base_link frame).
    # The UR URDF has a Rz(π) rotation between base_link and the kinematic
    # chain root (base_link_inertia).  The screw axes and M_home are defined
    # in the base_link frame so that FK output matches the URDF TF tree.
    params.M_home = np.array([
        [-1, 0, 0, (L1 + L2)],
        [0, 0, 1, (W1 + H2)],
        [0, 1, 0, H1 - W2],
        [0, 0, 0, 1]
    ])

    # Screw axes in space frame (base_link frame, matching URDF TF).
    # All UR URDF joints have axis=[0,0,1] in local frame; the accumulated
    # origin RPY transforms (including the base_link→base_link_inertia Rz(π))
    # produce these world-frame axes.
    params.screw_axes_space = np.array([
        [0, 0, 1, 0, 0, 0],                      # Joint 1: Z at origin
        [0, 1, 0, -H1, 0, 0],                     # Joint 2: +Y at (0,0,H1)
        [0, 1, 0, -H1, 0, L1],                    # Joint 3: +Y at (L1,0,H1)
        [0, 1, 0, -H1, 0, L1 + L2],               # Joint 4: +Y at (L1+L2,W1,H1)
        [0, 0, -1, -W1, (L1 + L2), 0],            # Joint 5: -Z at (L1+L2,W1,H1-W2)
        [0, 1, 0, -(H1 - W2), 0, L1 + L2],        # Joint 6: +Y at (L1+L2,W1+H2,H1-W2)
    ]).T  # Transpose to get 6x6 (each column is a screw axis)

    # Compute body frame screw axes
    params.screw_axes_body = _space_to_body_screws(
        params.screw_axes_space, params.M_home
    )

    # Joint limits
    params.joint_limits = [(-2*np.pi, 2*np.pi)] * 6

    # Dynamic parameters
    params.link_masses = np.array([3.761, 8.058, 2.846, 1.37, 1.3, 0.365])
    params.link_com = [
        np.array([0, -0.02561, 0.00193]),
        np.array([0.2125, 0, 0.11336]),
        np.array([0.15, 0.0, 0.0265]),
        np.array([0, -0.0018, 0.01634]),
        np.array([0, 0.0018, 0.01634]),
        np.array([0, 0, -0.001159]),
    ]

    return params


def create_ur3e_parameters() -> RobotParameters:
    """Create parameters for UR3e robot."""
    params = RobotParameters()
    params.model_name = "ur3e"
    params.num_joints = 6

    params.a = np.array([0.0, -0.24355, -0.2132, 0.0, 0.0, 0.0])
    params.d = np.array([0.15185, 0.0, 0.0, 0.13105, 0.08535, 0.0921])
    params.alpha = np.array([np.pi/2, 0.0, 0.0, np.pi/2, -np.pi/2, 0.0])

    L1, L2 = 0.24355, 0.2132
    W1, W2 = 0.13105, 0.08535
    H1, H2 = 0.15185, 0.0921

    params.link_lengths = {'L1': L1, 'L2': L2, 'W1': W1, 'W2': W2, 'H1': H1, 'H2': H2}
    params.M_home = np.array([
        [-1, 0, 0, (L1 + L2)],
        [0, 0, 1, (W1 + H2)],
        [0, 1, 0, H1 - W2],
        [0, 0, 0, 1]
    ])

    params.screw_axes_space = np.array([
        [0, 0, 1, 0, 0, 0],
        [0, 1, 0, -H1, 0, 0],
        [0, 1, 0, -H1, 0, L1],
        [0, 1, 0, -H1, 0, L1 + L2],
        [0, 0, -1, -W1, (L1 + L2), 0],
        [0, 1, 0, -(H1 - W2), 0, L1 + L2],
    ]).T

    params.screw_axes_body = _space_to_body_screws(
        params.screw_axes_space, params.M_home
    )
    params.joint_limits = [(-2*np.pi, 2*np.pi)] * 6

    return params


def create_ur10e_parameters() -> RobotParameters:
    """Create parameters for UR10e robot."""
    params = RobotParameters()
    params.model_name = "ur10e"
    params.num_joints = 6

    params.a = np.array([0.0, -0.6127, -0.57155, 0.0, 0.0, 0.0])
    params.d = np.array([0.1807, 0.0, 0.0, 0.17415, 0.11985, 0.11655])
    params.alpha = np.array([np.pi/2, 0.0, 0.0, np.pi/2, -np.pi/2, 0.0])

    L1, L2 = 0.6127, 0.57155
    W1, W2 = 0.17415, 0.11985
    H1, H2 = 0.1807, 0.11655

    params.link_lengths = {'L1': L1, 'L2': L2, 'W1': W1, 'W2': W2, 'H1': H1, 'H2': H2}
    params.M_home = np.array([
        [-1, 0, 0, (L1 + L2)],
        [0, 0, 1, (W1 + H2)],
        [0, 1, 0, H1 - W2],
        [0, 0, 0, 1]
    ])

    params.screw_axes_space = np.array([
        [0, 0, 1, 0, 0, 0],
        [0, 1, 0, -H1, 0, 0],
        [0, 1, 0, -H1, 0, L1],
        [0, 1, 0, -H1, 0, L1 + L2],
        [0, 0, -1, -W1, (L1 + L2), 0],
        [0, 1, 0, -(H1 - W2), 0, L1 + L2],
    ]).T

    params.screw_axes_body = _space_to_body_screws(
        params.screw_axes_space, params.M_home
    )
    params.joint_limits = [(-2*np.pi, 2*np.pi)] * 6

    return params


def create_ur16e_parameters() -> RobotParameters:
    """Create parameters for UR16e robot."""
    params = RobotParameters()
    params.model_name = "ur16e"
    params.num_joints = 6

    params.a = np.array([0.0, -0.4784, -0.36, 0.0, 0.0, 0.0])
    params.d = np.array([0.1807, 0.0, 0.0, 0.17415, 0.11985, 0.11655])
    params.alpha = np.array([np.pi/2, 0.0, 0.0, np.pi/2, -np.pi/2, 0.0])

    L1, L2 = 0.4784, 0.36
    W1, W2 = 0.17415, 0.11985
    H1, H2 = 0.1807, 0.11655

    params.link_lengths = {'L1': L1, 'L2': L2, 'W1': W1, 'W2': W2, 'H1': H1, 'H2': H2}
    params.M_home = np.array([
        [-1, 0, 0, (L1 + L2)],
        [0, 0, 1, (W1 + H2)],
        [0, 1, 0, H1 - W2],
        [0, 0, 0, 1]
    ])

    params.screw_axes_space = np.array([
        [0, 0, 1, 0, 0, 0],
        [0, 1, 0, -H1, 0, 0],
        [0, 1, 0, -H1, 0, L1],
        [0, 1, 0, -H1, 0, L1 + L2],
        [0, 0, -1, -W1, (L1 + L2), 0],
        [0, 1, 0, -(H1 - W2), 0, L1 + L2],
    ]).T

    params.screw_axes_body = _space_to_body_screws(
        params.screw_axes_space, params.M_home
    )
    params.joint_limits = [(-2*np.pi, 2*np.pi)] * 6

    return params


# Factory function mapping
_ROBOT_FACTORIES = {
    'ur3e': create_ur3e_parameters,
    'ur5e': create_ur5e_parameters,
    'ur10e': create_ur10e_parameters,
    'ur16e': create_ur16e_parameters,
}


def load_robot_parameters(model_name: str = None,
                          config_path: str = None) -> RobotParameters:
    """
    Load robot parameters by model name or from config file.

    Args:
        model_name: Robot model name (e.g., 'ur5e')
        config_path: Path to YAML configuration file

    Returns:
        RobotParameters instance
    """
    if config_path:
        return _load_from_yaml(config_path)

    if model_name is None:
        model_name = 'ur5e'

    model_name = model_name.lower()
    if model_name not in _ROBOT_FACTORIES:
        raise ValueError(
            f"Unknown robot model: {model_name}. "
            f"Supported: {list(_ROBOT_FACTORIES.keys())}"
        )

    return _ROBOT_FACTORIES[model_name]()


def get_supported_models() -> List[str]:
    """Get list of supported robot model names."""
    return list(_ROBOT_FACTORIES.keys())


def _load_from_yaml(config_path: str) -> RobotParameters:
    """Load parameters from YAML configuration file."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, 'r') as f:
        config = yaml.safe_load(f)

    params = RobotParameters()

    # Load basic info
    robot_config = config.get('robot', {})
    params.model_name = robot_config.get('model_name', 'custom')
    params.num_joints = robot_config.get('num_joints', 6)

    # Load DH parameters
    dh = config.get('dh_parameters', {})
    params.a = np.array(dh.get('a', [0]*6))
    params.d = np.array(dh.get('d', [0]*6))
    params.alpha = np.array(dh.get('alpha', [0]*6))

    # Load link parameters
    link_params = config.get('link_parameters', {})
    params.link_lengths = {k: v for k, v in link_params.items()}

    # Load home configuration
    if 'home_configuration' in config:
        params.M_home = np.array(config['home_configuration'])

    # Load screw axes
    if 'screw_axes_space' in config:
        params.screw_axes_space = np.array(config['screw_axes_space']).T

    # Load joint limits
    if 'joint_limits' in config:
        limits = config['joint_limits']
        params.joint_limits = [
            (limits[f'joint_{i+1}'][0], limits[f'joint_{i+1}'][1])
            for i in range(6)
        ]

    # Compute body screws if not provided
    if params.screw_axes_space is not None and params.M_home is not None:
        params.screw_axes_body = _space_to_body_screws(
            params.screw_axes_space, params.M_home
        )

    return params


def _skew3(v: np.ndarray) -> np.ndarray:
    """Create 3x3 skew-symmetric matrix from 3-vector."""
    return np.array([
        [0, -v[2], v[1]],
        [v[2], 0, -v[0]],
        [-v[1], v[0], 0]
    ])


def _adjoint(T: np.ndarray) -> np.ndarray:
    """Compute 6x6 adjoint representation of SE(3) transformation."""
    R = T[:3, :3]
    p = T[:3, 3]

    Ad = np.zeros((6, 6))
    Ad[:3, :3] = R
    Ad[3:, :3] = _skew3(p) @ R
    Ad[3:, 3:] = R

    return Ad


def _space_to_body_screws(screw_axes_space: np.ndarray,
                          M_home: np.ndarray) -> np.ndarray:
    """Convert space frame screw axes to body frame."""
    R = M_home[:3, :3]
    p = M_home[:3, 3]

    # M_inv
    M_inv = np.eye(4)
    M_inv[:3, :3] = R.T
    M_inv[:3, 3] = -R.T @ p

    Ad_M_inv = _adjoint(M_inv)

    return Ad_M_inv @ screw_axes_space
