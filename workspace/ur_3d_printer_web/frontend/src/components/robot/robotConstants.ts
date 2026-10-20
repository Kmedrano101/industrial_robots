import type { RobotModel } from '../../stores/useSettingsStore';

export const ROBOT_MODELS: { value: RobotModel; label: string }[] = [
  { value: 'ur3e', label: 'UR3e' },
  { value: 'ur5e', label: 'UR5e' },
  { value: 'ur7e', label: 'UR7e' },
  { value: 'ur10e', label: 'UR10e' },
  { value: 'ur16e', label: 'UR16e' },
  { value: 'ur20', label: 'UR20' },
  { value: 'ur30', label: 'UR30' },
];

export const JOINT_LABELS = [
  'Shoulder Pan',
  'Shoulder Lift',
  'Elbow',
  'Wrist 1',
  'Wrist 2',
  'Wrist 3',
];

export const JOG_DEGREES = [-5, -1, 1, 5];

export function rad2deg(r: number): number {
  return (r * 180) / Math.PI;
}

export function deg2rad(d: number): number {
  return (d * Math.PI) / 180;
}
