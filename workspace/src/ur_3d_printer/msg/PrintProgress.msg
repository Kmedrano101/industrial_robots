# Print progress message

std_msgs/Header header

# Current layer (0-based)
int32 current_layer

# Total number of layers
int32 total_layers

# Progress within current layer (0.0 to 1.0)
float32 layer_progress

# Overall progress (0.0 to 1.0)
float32 overall_progress

# Elapsed time (seconds)
float64 elapsed_time

# Estimated remaining time (seconds)
float64 estimated_remaining

# Current Z height (meters)
float64 current_z_height
