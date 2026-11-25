#!/usr/bin/env python3
"""Joy -> /cmd_vel 遥控桥。

两种输入源都能用（改 joy_topic 即可）：
  /joy                        手柄插 Jetson，由 linux_joy 节点发布
  /ros_robot_controller/joy   手柄插 RRC-M4 的 USB HOST 口，板子固件上报

安全设计：
  - 死手开关（enable_button >= 0 时必须按住才发速度）
  - 摇杆死区
  - 速度限幅（默认 0.15 m/s / 0.4 rad/s，底盘自身还会再限 0.2 / 0.5）
  - 0.5s 收不到 Joy 就发零速
"""
import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from sensor_msgs.msg import Joy


class JoyTeleop(Node):
    def __init__(self):
        super().__init__('joy_teleop')
        self.declare_parameter('joy_topic', '/joy')
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')
        # 默认值按飞智八爪鱼5 + xpad 实测（与 config/teleop.yaml 保持一致）
        self.declare_parameter('axis_linear', 1)
        self.declare_parameter('axis_angular', 3)
        self.declare_parameter('enable_button', -1)
        self.declare_parameter('invert_linear', True)
        self.declare_parameter('invert_angular', True)
        self.declare_parameter('scale_linear', 0.15)
        self.declare_parameter('scale_angular', 0.4)
        self.declare_parameter('deadzone', 0.08)
        self.declare_parameter('timeout', 0.5)

        p = self.get_parameter
        self.axis_linear = int(p('axis_linear').value)
        self.axis_angular = int(p('axis_angular').value)
        self.enable_button = int(p('enable_button').value)
        self.invert_linear = bool(p('invert_linear').value)
        self.invert_angular = bool(p('invert_angular').value)
        self.scale_linear = float(p('scale_linear').value)
        self.scale_angular = float(p('scale_angular').value)
        self.deadzone = float(p('deadzone').value)
        self.timeout = float(p('timeout').value)

        self.joy = None
        self.last_rx = self.get_clock().now()
        self.pub = self.create_publisher(Twist, p('cmd_vel_topic').value, 10)
        self.create_subscription(Joy, p('joy_topic').value, self.on_joy, 10)
        self.create_timer(0.05, self.tick)

        self.get_logger().info(
            'joy_teleop: %s -> %s (linear=axis%d, angular=axis%d, deadman=%s)'
            % (p('joy_topic').value, p('cmd_vel_topic').value,
               self.axis_linear, self.axis_angular,
               '无' if self.enable_button < 0 else 'button%d' % self.enable_button))

    def on_joy(self, msg):
        self.joy = msg
        self.last_rx = self.get_clock().now()

    def axis(self, idx, invert):
        if idx < 0 or idx >= len(self.joy.axes):
            return 0.0
        value = self.joy.axes[idx]
        if abs(value) < self.deadzone:
            return 0.0
        # 去掉死区后重新映射到 0..1，避免死区边缘跳变
        value = (abs(value) - self.deadzone) / (1.0 - self.deadzone) * (1 if value > 0 else -1)
        return -value if invert else value

    def tick(self):
        msg = Twist()
        stale = (self.get_clock().now() - self.last_rx).nanoseconds / 1e9 > self.timeout
        if self.joy is not None and not stale:
            enabled = (self.enable_button < 0
                       or (self.enable_button < len(self.joy.buttons)
                           and self.joy.buttons[self.enable_button]))
            if enabled:
                msg.linear.x = self.axis(self.axis_linear, self.invert_linear) * self.scale_linear
                msg.angular.z = self.axis(self.axis_angular, self.invert_angular) * self.scale_angular
        self.pub.publish(msg)


def main():
    rclpy.init()
    node = JoyTeleop()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
