#!/usr/bin/env python3
"""读取 Linux 手柄设备 (/dev/input/jsX) 并发布 sensor_msgs/Joy。

替代 ROS 的 joy 包：容器是精简 ros-base，没有 joy；本节点只用标准库 + rclpy。
手柄插在 Jetson 的 USB 口上即可（不是控制板）。

js_event 结构（Linux 内核）：
    __u32 time; __s16 value; __u8 type; __u8 number;   -> 8 字节
"""
import os
import struct

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy

EVENT_FMT = '<IhBB'
EVENT_SIZE = struct.calcsize(EVENT_FMT)
JS_EVENT_BUTTON = 0x01
JS_EVENT_AXIS = 0x02
JS_EVENT_INIT = 0x80


class LinuxJoy(Node):
    def __init__(self):
        super().__init__('linux_joy')
        self.declare_parameter('device', '/dev/input/js0')
        self.declare_parameter('num_axes', 8)
        self.declare_parameter('num_buttons', 16)
        self.declare_parameter('publish_rate', 50.0)
        self.declare_parameter('topic', 'joy')

        self.device = self.get_parameter('device').value
        self.axes = [0.0] * int(self.get_parameter('num_axes').value)
        self.buttons = [0] * int(self.get_parameter('num_buttons').value)
        rate = float(self.get_parameter('publish_rate').value)

        self.pub = self.create_publisher(Joy, self.get_parameter('topic').value, 10)
        self.fd = None
        self.buf = b''

        self.open_fails = 0
        self.create_timer(1.0 / max(rate, 1.0), self.publish)
        self.create_timer(1.0, self.ensure_open)
        self.ensure_open()

    def ensure_open(self):
        if self.fd is not None:
            return
        try:
            self.fd = os.open(self.device, os.O_RDONLY | os.O_NONBLOCK)
            self.open_fails = 0
            self.get_logger().info('已打开手柄设备 %s' % self.device)
        except OSError as exc:
            self.open_fails += 1
            # 每 30 秒提示一次，避免刷屏
            if self.open_fails == 1 or self.open_fails % 30 == 0:
                self.get_logger().warn(
                    '打不开 %s: %s（等待手柄插入）' % (self.device, exc))

    def poll(self):
        if self.fd is None:
            return
        try:
            chunk = os.read(self.fd, EVENT_SIZE * 128)
        except BlockingIOError:
            return
        except OSError as exc:
            self.get_logger().warn('读手柄失败: %s' % exc)
            os.close(self.fd)
            self.fd = None
            return
        if not chunk:
            return
        self.buf += chunk
        while len(self.buf) >= EVENT_SIZE:
            _t, value, etype, number = struct.unpack(EVENT_FMT, self.buf[:EVENT_SIZE])
            self.buf = self.buf[EVENT_SIZE:]
            etype &= 0x7F  # 去掉 INIT 标志
            if etype == JS_EVENT_AXIS and number < len(self.axes):
                self.axes[number] = max(-1.0, value / 32767.0)
            elif etype == JS_EVENT_BUTTON and number < len(self.buttons):
                self.buttons[number] = 1 if value else 0

    def publish(self):
        self.poll()
        msg = Joy()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.axes = list(self.axes)
        msg.buttons = list(self.buttons)
        self.pub.publish(msg)


def main():
    rclpy.init()
    node = LinuxJoy()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node.fd is not None:
            os.close(node.fd)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
