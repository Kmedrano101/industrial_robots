# Extruder state message — published by extruder_controller at publish_rate.
#
# The first five fields are the original contract (print_node and the web
# bridge read them); the rest describe multi-zone hardware such as pellet
# screw extruders. `temperature` / `target_temperature` mirror zone 0.

std_msgs/Header header

# Extruder state
uint8 state
uint8 OFF = 0
uint8 EXTRUDING = 1
uint8 RETRACTING = 2
uint8 PRIMING = 3
uint8 HEATING = 4
uint8 PURGING = 5
uint8 FAULT = 6

# Current extrusion rate (m^3/s) — legacy units, equals flow_mm3_s * 1e-9
float64 extrusion_rate

# Current temperature of zone 0 (Celsius, 0 if not applicable)
float64 temperature

# Target temperature of zone 0 (Celsius, 0 if not applicable)
float64 target_temperature

# Whether every heated zone is at its target (true when there are no heaters)
bool at_temperature

# ── Extended telemetry ───────────────────────────────────────────────────
# Commanded and measured volumetric flow (mm^3/s); negative = reverse
float64 target_flow_mm3_s
float64 flow_mm3_s

# Per heated zone, same order as ExtruderInfo.zone_names
float64[] zone_temperatures
float64[] zone_targets
float64[] zone_heater_duty      # 0..1, when the driver reports it

# Part-cooling / barrel fan, 0..100
float64 fan_percent

# True while any zone has a target > 0
bool heaters_on

# True when the extruder may be commanded to extrude right now
# (heated zones at temperature, no fault, driver alive)
bool ready

# Non-empty while state == FAULT; cleared by ~/reset_fault
string fault
