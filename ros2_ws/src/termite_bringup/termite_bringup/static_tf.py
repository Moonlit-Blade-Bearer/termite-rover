#!/usr/bin/env python3
"""持续发布静态 TF。

Humble 自带的 static_transform_publisher 在部分情况下只发一次、后启动的
监听者收不到，故用本节点以 TRANSIENT_LOCAL QoS 周期性重发。

坐标约定（全部零偏移，待实测后填）：
  base_footprint -> base_link   底盘基准面到车体
  base_link      -> imu_link    板载 IMU 安装位
  base_link      -> laser       雷达安装位
"""
import math

import rclpy
from geometry_msgs.msg import TransformStamped
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile
from tf2_msgs.msg import TFMessage

# (parent, child, x, y, z, yaw)
STATIC_TRANSFORMS = [
    ('base_footprint', 'base_link', 0.0, 0.0, 0.0, 0.0),
    ('base_link', 'imu_link', 0.0, 0.0, 0.0, 0.0),
    ('base_link', 'laser', 0.0, 0.0, 0.0, 0.0),
]


class StaticTf(Node):
    def __init__(self):
        super().__init__('static_tf_pub')
        qos = QoSProfile(depth=10, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL)
        self.pub = self.create_publisher(TFMessage, '/tf_static', qos)
        self.msg = TFMessage()
        for parent, child, x, y, z, yaw in STATIC_TRANSFORMS:
            t = TransformStamped()
            t.header.frame_id = parent
            t.child_frame_id = child
            t.transform.translation.x = x
            t.transform.translation.y = y
            t.transform.translation.z = z
            t.transform.rotation.z = math.sin(yaw / 2.0)
            t.transform.rotation.w = math.cos(yaw / 2.0)
            self.msg.transforms.append(t)
        self.create_timer(1.0, self.publish)

    def publish(self):
        now = self.get_clock().now().to_msg()
        for t in self.msg.transforms:
            t.header.stamp = now
        self.pub.publish(self.msg)


def main():
    rclpy.init()
    node = StaticTf()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
