#!/usr/bin/env python3
"""临时诊断：记录 /cmd_vel_test 的变化，用于核对摇杆方向。"""
import sys
import time

import rclpy
from geometry_msgs.msg import Twist

TOPIC = sys.argv[1] if len(sys.argv) > 1 else '/cmd_vel_test'
DURATION = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0

rclpy.init()
node = rclpy.create_node('twist_capture')
state = {'last': None, 't0': time.time()}


def cb(msg):
    cur = (round(msg.linear.x, 3), round(msg.angular.z, 3))
    if cur != state['last']:
        state['last'] = cur
        print('%.1fs linear.x=%+.3f angular.z=%+.3f' % (
            time.time() - state['t0'], cur[0], cur[1]), flush=True)


node.create_subscription(Twist, TOPIC, cb, 10)
end = time.time() + DURATION
while time.time() < end:
    rclpy.spin_once(node, timeout_sec=0.2)
node.destroy_node()
rclpy.shutdown()
