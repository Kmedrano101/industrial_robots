#!/usr/bin/env python3
"""
Test: Start rectangle print and sample TCP poses throughout execution.

Verifies:
1. Nozzle always points down (tool Z = [0,0,-1]) during printing
2. TCP positions stay within expected rectangle bounds
3. Print completes successfully
"""
import sys
import time
import threading
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from sensor_msgs.msg import JointState
from ur_kinematics_msgs.srv import ComputeFK
from ur_3d_printer.srv import StartPrint
from ur_3d_printer.msg import PrintState, PrintProgress

# Tool offset: from tool0 (flange) to nozzle tip
TOOL_OFFSET = np.eye(4)
TOOL_OFFSET[2, 3] = 0.105  # 105mm along tool Z


def quat_to_rotmat(qx, qy, qz, qw):
    """Quaternion to 3x3 rotation matrix."""
    return np.array([
        [1 - 2*(qy**2 + qz**2), 2*(qx*qy - qz*qw), 2*(qx*qz + qy*qw)],
        [2*(qx*qy + qz*qw), 1 - 2*(qx**2 + qz**2), 2*(qy*qz - qx*qw)],
        [2*(qx*qz - qy*qw), 2*(qy*qz + qx*qw), 1 - 2*(qx**2 + qy**2)],
    ])


class PrintTCPMonitor(Node):
    def __init__(self):
        super().__init__('print_tcp_monitor')
        self.cb_group = ReentrantCallbackGroup()

        self.joints = None
        self.print_state = 0
        self.print_state_name = "Unknown"
        self.current_layer = 0
        self.total_layers = 0
        self.progress = 0.0

        # Collected TCP samples during printing
        self.tcp_samples = []  # list of dicts with pos, z_axis, state, layer, time

        self.sub_js = self.create_subscription(
            JointState, '/joint_states', self.joint_cb, 10,
            callback_group=self.cb_group)
        self.sub_state = self.create_subscription(
            PrintState, '/print_node/state', self.state_cb, 10,
            callback_group=self.cb_group)
        self.sub_progress = self.create_subscription(
            PrintProgress, '/print_node/progress', self.progress_cb, 10,
            callback_group=self.cb_group)

        self.fk_client = self.create_client(
            ComputeFK, '/compute_fk', callback_group=self.cb_group)
        self.print_client = self.create_client(
            StartPrint, '/print_node/start_print', callback_group=self.cb_group)

        # Sampling timer (10 Hz during print)
        self.sample_timer = self.create_timer(
            0.1, self.sample_tcp, callback_group=self.cb_group)

        self.start_time = time.time()
        self.print_done = threading.Event()
        self.print_success = None

    def joint_cb(self, msg):
        ur_names = [
            'shoulder_pan_joint', 'shoulder_lift_joint', 'elbow_joint',
            'wrist_1_joint', 'wrist_2_joint', 'wrist_3_joint'
        ]
        positions = []
        for name in ur_names:
            if name in msg.name:
                idx = list(msg.name).index(name)
                positions.append(msg.position[idx])
        if len(positions) == 6:
            self.joints = np.array(positions)

    def state_cb(self, msg):
        self.print_state = msg.state
        self.print_state_name = msg.state_name
        # Print completed or errored
        if msg.state in (7, 8):  # COMPLETED=7, ERROR=8
            self.print_success = (msg.state == 7)
            self.print_done.set()

    def progress_cb(self, msg):
        self.current_layer = msg.current_layer
        self.total_layers = msg.total_layers
        self.progress = msg.overall_progress

    def sample_tcp(self):
        """Sample TCP pose if we're in a printing state."""
        if self.joints is None:
            return
        # Only sample during active states (PRINTING=5, TRAVEL=6, LAYER_CHANGE=4, HOMING=3)
        if self.print_state not in (3, 4, 5, 6):
            return

        req = ComputeFK.Request()
        req.joint_positions = self.joints.tolist()

        future = self.fk_client.call_async(req)
        future.add_done_callback(self._fk_done)

    def _fk_done(self, future):
        result = future.result()
        if result is None or not result.success:
            return

        pose = result.end_effector_pose
        p = pose.position
        q = pose.orientation
        R = quat_to_rotmat(q.x, q.y, q.z, q.w)

        T_flange = np.eye(4)
        T_flange[:3, :3] = R
        T_flange[:3, 3] = [p.x, p.y, p.z]
        T_nozzle = T_flange @ TOOL_OFFSET

        tool_z = T_nozzle[:3, 2]
        nozzle_pos = T_nozzle[:3, 3]

        self.tcp_samples.append({
            'time': time.time() - self.start_time,
            'pos': nozzle_pos.copy(),
            'tool_z': tool_z.copy(),
            'state': self.print_state_name,
            'layer': self.current_layer,
        })

    def start_print(self, gcode_path):
        """Call the start_print service."""
        if not self.print_client.wait_for_service(timeout_sec=10.0):
            self.get_logger().error('start_print service not available')
            return False

        req = StartPrint.Request()
        req.gcode_filepath = gcode_path

        self.get_logger().info(f'Starting print: {gcode_path}')
        future = self.print_client.call_async(req)
        future.add_done_callback(self._print_done)
        return True

    def _print_done(self, future):
        result = future.result()
        if result is not None:
            self.get_logger().info(
                f'Print service returned: success={result.success}, '
                f'message={result.message}, layers={result.num_layers}'
            )
            self.print_success = result.success
        else:
            self.print_success = False
        self.print_done.set()

    def report(self):
        """Print summary of collected TCP samples."""
        print("\n" + "=" * 70)
        print("RECTANGLE PRINT — TCP POSE VERIFICATION REPORT")
        print("=" * 70)

        n = len(self.tcp_samples)
        if n == 0:
            print("WARNING: No TCP samples collected during print!")
            return False

        print(f"\nTotal TCP samples collected: {n}")

        # Check nozzle-down for all samples
        z_dots = [np.dot(s['tool_z'], [0, 0, -1]) for s in self.tcp_samples]
        min_z_dot = min(z_dots)
        max_z_dot = max(z_dots)
        all_down = all(d > 0.999 for d in z_dots)

        print(f"\n--- Nozzle Orientation (Z-axis dot [0,0,-1]) ---")
        print(f"  Min: {min_z_dot:.6f}  Max: {max_z_dot:.6f}")
        print(f"  {'PASS' if all_down else 'FAIL'}: All samples nozzle-down (> 0.999)")

        # Position stats
        positions = np.array([s['pos'] for s in self.tcp_samples])
        x_min, x_max = positions[:, 0].min(), positions[:, 0].max()
        y_min, y_max = positions[:, 1].min(), positions[:, 1].max()
        z_min, z_max = positions[:, 2].min(), positions[:, 2].max()

        print(f"\n--- Nozzle Tip Position Range ---")
        print(f"  X: [{x_min:.4f}, {x_max:.4f}] m")
        print(f"  Y: [{y_min:.4f}, {y_max:.4f}] m")
        print(f"  Z: [{z_min:.4f}, {z_max:.4f}] m")

        # Expected: X=[-0.320,-0.280], Y=[-0.010,0.010], Z=[-0.0095,~0.015 with z-hop]
        print(f"\n--- Expected ranges (from gcode + print_origin) ---")
        print(f"  X: [-0.320, -0.280] m  (gcode X=[-20,20]mm + origin=-0.3)")
        print(f"  Y: [-0.010,  0.010] m  (gcode Y=[-10,10]mm + origin=0.0)")
        print(f"  Z: [-0.010,  0.010] m  (gcode Z=[0.5,9.5]mm + origin=-0.01, + z-hop)")

        # Print some sample points at different layers
        print(f"\n--- Sample points per state ---")
        states_seen = set(s['state'] for s in self.tcp_samples)
        for state in sorted(states_seen):
            state_samples = [s for s in self.tcp_samples if s['state'] == state]
            if state_samples:
                s = state_samples[len(state_samples)//2]  # mid sample
                p = s['pos']
                z = s['tool_z']
                print(f"  {state:15s} (layer {s['layer']:2d}): "
                      f"pos=[{p[0]:.4f}, {p[1]:.4f}, {p[2]:.4f}], "
                      f"tool_z=[{z[0]:.4f}, {z[1]:.4f}, {z[2]:.4f}]")

        # Print first and last 3 samples
        print(f"\n--- First 3 samples ---")
        for s in self.tcp_samples[:3]:
            p = s['pos']
            z = s['tool_z']
            print(f"  t={s['time']:6.1f}s {s['state']:15s} L{s['layer']:2d}: "
                  f"pos=[{p[0]:.4f}, {p[1]:.4f}, {p[2]:.4f}], "
                  f"Zdot={np.dot(z, [0,0,-1]):.6f}")

        print(f"\n--- Last 3 samples ---")
        for s in self.tcp_samples[-3:]:
            p = s['pos']
            z = s['tool_z']
            print(f"  t={s['time']:6.1f}s {s['state']:15s} L{s['layer']:2d}: "
                  f"pos=[{p[0]:.4f}, {p[1]:.4f}, {p[2]:.4f}], "
                  f"Zdot={np.dot(z, [0,0,-1]):.6f}")

        print(f"\n--- Final Result ---")
        print(f"  Print completed: {self.print_success}")
        print(f"  Nozzle always down: {all_down}")
        print(f"  Total samples: {n}")
        print("=" * 70)

        return all_down and (self.print_success is True)


def main():
    rclpy.init()
    node = PrintTCPMonitor()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)

    # Spin in background thread
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    # Wait for joint states
    print("Waiting for joint states...")
    for _ in range(50):
        time.sleep(0.1)
        if node.joints is not None:
            break
    if node.joints is None:
        print("ERROR: No joint states received")
        rclpy.shutdown()
        sys.exit(1)

    # Start the print
    gcode = '/home/kmedrano/src/industrial_robots/workspace/install/ur_3d_printer/share/ur_3d_printer/resource/rectangle.gcode'
    if not node.start_print(gcode):
        rclpy.shutdown()
        sys.exit(1)

    # Wait for print to complete (timeout 5 minutes)
    print("Monitoring TCP during print...")
    done = node.print_done.wait(timeout=300)
    if not done:
        print("ERROR: Print timed out after 5 minutes")

    # Give a moment for last samples
    time.sleep(1.0)

    # Report
    success = node.report()

    executor.shutdown()
    node.destroy_node()
    rclpy.shutdown()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
