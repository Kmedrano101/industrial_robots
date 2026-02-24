# Print state machine status

std_msgs/Header header

# Current state
uint8 state

# State constants
uint8 IDLE = 0
uint8 LOADING_GCODE = 1
uint8 VALIDATING = 2
uint8 HOMING = 3
uint8 CALIBRATING = 4
uint8 PRINTING = 5
uint8 TRAVEL_MOVE = 6
uint8 LAYER_CHANGE = 7
uint8 COMPLETED = 8
uint8 PAUSED = 9
uint8 CANCELLING = 10
uint8 ERROR = 11

# Human-readable state name
string state_name

# Error message (if state == ERROR)
string error_message
