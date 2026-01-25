# Pick and place state machine status

std_msgs/Header header

# Current state
uint8 state

# State constants
uint8 IDLE = 0
uint8 MOVING_TO_PICK = 1
uint8 APPROACHING_PICK = 2
uint8 GRASPING = 3
uint8 RETRACTING_PICK = 4
uint8 MOVING_TO_PLACE = 5
uint8 APPROACHING_PLACE = 6
uint8 RELEASING = 7
uint8 RETRACTING_PLACE = 8
uint8 RETURNING_HOME = 9
uint8 SUCCESS = 10
uint8 ERROR = 11

# Human-readable state name
string state_name

# Progress within current operation (0.0 to 1.0)
float32 progress

# Error message (if state == ERROR)
string error_message
