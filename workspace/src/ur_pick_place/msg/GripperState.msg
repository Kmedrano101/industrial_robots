# Gripper state message

std_msgs/Header header

# Gripper state: OPEN=0, CLOSED=1, MOVING=2
uint8 state
uint8 OPEN = 0
uint8 CLOSED = 1
uint8 MOVING = 2

# Gripper position (0.0 = closed, 1.0 = fully open)
float64 position

# Object detected between fingers (simulated)
bool object_detected
