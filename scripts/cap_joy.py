#!/usr/bin/env python3
"""临时诊断：把 /joy 的轴变化带时间戳打到 stdout，用于确定轴编号。"""
import sys
import time

import rclpy
from sensor_msgs.msg import Joy

DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 120.0

rclpy.init()
node = rclpy.create_node('joy_capture')
state = {'last': None, 't0': time.time()}


def cb(msg):
    axes = [round(a, 2) for a in msg.axes]
    if axes != state['last']:
        state['last'] = axes
        print('%.1fs axes=%s buttons=%s' % (
            time.time() - state['t0'], axes, list(msg.buttons)), flush=True)


node.create_subscription(Joy, '/joy', cb, 10)
end = time.time() + DURATION
while time.time() < end:
    rclpy.spin_once(node, timeout_sec=0.2)
node.destroy_node()
rclpy.shutdown()
