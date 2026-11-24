#!/usr/bin/env python3
"""持续发布静态 TF：base_footprint->base_link, base_link->imu_link。
Humble 的 static_transform_publisher 只发一次，后启动的监听者收不到，故用此节点。"""
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSDurabilityPolicy
from geometry_msgs.msg import TransformStamped
from tf2_msgs.msg import TFMessage


class StaticTf(Node):
    def __init__(self):
        super().__init__('static_tf_pub')
        qos = QoSProfile(depth=10, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL)
        self.pub = self.create_publisher(TFMessage, '/tf_static', qos)
        self.msg = TFMessage()
        for parent, child in [('base_footprint', 'base_link'), ('base_link', 'imu_link')]:
            t = TransformStamped()
            t.header.frame_id = parent
            t.child_frame_id = child
            t.transform.rotation.w = 1.0
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
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
