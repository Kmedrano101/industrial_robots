/** Generic UR "elbow up" pose — a sane, upright default distinct from the
 *  all-zero joint pose. On a UR arm, all-zero joints means the upper arm
 *  and forearm point straight out horizontally (shoulder_lift=0), which
 *  reads as "the robot is lying down" rather than a neutral/parked stance.
 *
 *  Used as: (1) the RobotModel viewer's fallback pose whenever there's no
 *  real live joint data to show (disconnected — see RobotModel.tsx), and
 *  (2) the Robot page's simulation's initial pose before the real
 *  HOME_POSES value has loaded from the backend (see RobotPage.tsx). */
export const GENERIC_UP_POSE = [0, -Math.PI / 2, Math.PI / 2, -Math.PI / 2, -Math.PI / 2, 0];
