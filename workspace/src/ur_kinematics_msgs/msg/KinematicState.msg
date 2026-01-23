# Complete kinematic state of the robot

std_msgs/Header header

# Current joint configuration
float64[6] joint_positions
float64[6] joint_velocities

# End-effector pose
geometry_msgs/Pose end_effector_pose

# End-effector twist (velocity)
geometry_msgs/Twist end_effector_twist

# Jacobian condition number (singularity indicator)
float64 condition_number

# Manipulability measure
float64 manipulability

# Flag indicating if near singularity
bool near_singularity
