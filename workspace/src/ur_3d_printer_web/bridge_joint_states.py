#!/usr/bin/env python3
"""Bridge /joint_states from ROS2 to the web backend via HTTP POST.

Run inside the ur-driver container:
  python3 /tmp/bridge_joint_states.py --backend http://172.20.0.1:8090
"""
import argparse, json, time, urllib.request
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState

JOINT_ORDER = [
    'shoulder_pan_joint', 'shoulder_lift_joint', 'elbow_joint',
    'wrist_1_joint', 'wrist_2_joint', 'wrist_3_joint',
]

class Bridge(Node):
    def __init__(self, url, rate):
        super().__init__('joint_bridge')
        self.url = url.rstrip('/') + '/api/bridge/joints'
        self.interval = 1.0 / rate
        self.last = 0.0
        self.create_subscription(JointState, '/joint_states', self.cb, 10)
        self.get_logger().info(f'Bridging → {self.url} at {rate} Hz')

    def cb(self, msg):
        now = time.time()
        if now - self.last < self.interval:
            return
        self.last = now
        pos = []
        for name in JOINT_ORDER:
            if name in msg.name:
                pos.append(msg.position[msg.name.index(name)])
        if len(pos) == 6:
            try:
                data = json.dumps({'positions': pos}).encode()
                req = urllib.request.Request(self.url, data=data,
                    headers={'Content-Type': 'application/json'}, method='POST')
                urllib.request.urlopen(req, timeout=1)
            except Exception:
                pass

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--backend', default='http://172.20.0.1:8090')
    p.add_argument('--rate', type=float, default=10.0)
    a = p.parse_args()
    rclpy.init()
    rclpy.spin(Bridge(a.backend, a.rate))
