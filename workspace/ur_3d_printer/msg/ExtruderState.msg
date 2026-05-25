# Extruder state message

std_msgs/Header header

# Extruder state
uint8 state
uint8 OFF = 0
uint8 EXTRUDING = 1
uint8 RETRACTING = 2
uint8 PRIMING = 3

# Current extrusion rate (m^3/s)
float64 extrusion_rate

# Current temperature (Celsius, 0 if not applicable)
float64 temperature

# Target temperature (Celsius, 0 if not applicable)
float64 target_temperature

# Whether extruder is at target temperature
bool at_temperature
