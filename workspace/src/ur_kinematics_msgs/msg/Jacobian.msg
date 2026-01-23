# 6x6 Jacobian matrix

std_msgs/Header header

# Jacobian matrix stored in row-major order
# J = [J11, J12, ..., J16, J21, ..., J66]
float64[36] data

# Frame of reference
string frame  # "space" or "body"

# Condition number
float64 condition_number

# Manipulability measure
float64 manipulability
