# Static description of the mounted extruder, published once (transient
# local) by extruder_controller so clients can adapt their UI/limits to the
# hardware instead of hard-coding one extruder type.

string name                       # "Mahor V5 M12 PRO"
string model                      # profile id, e.g. "mahor_v5_m12_pro"
string kind                       # pellet_screw | filament | paste
string driver                     # mock | gcode_serial | topic | ur_io
float64 nozzle_diameter_mm

# Heated zones (empty for unheated extruders)
string[] zone_names
float64[] zone_max_temperature
float64 min_extrusion_temperature  # cold-extrusion interlock, 0 = none
float64 at_temperature_tolerance

# Flow envelope (mm^3/s)
float64 max_flow_mm3_s
float64 default_flow_mm3_s

# Capabilities
bool has_heaters
bool has_temperature_feedback
bool has_fan
bool has_retract                  # false for screw extruders (coast instead)
bool has_purge

# Default purge routine (mm^3, mm^3/s)
float64 purge_volume_mm3
float64 purge_rate_mm3_s
