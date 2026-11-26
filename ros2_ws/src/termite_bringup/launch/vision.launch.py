"""K230 视觉接收：读 /dev/k230 的检测帧 → /detections (vision_msgs/Detection2DArray)。

K230 端需要先跑检测器（scripts/k230_detector.py），否则本节点只会空转重连。
"""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='termite_bringup',
            executable='vision_receiver',
            name='vision_receiver',
            output='screen',
            respawn=True,
            respawn_delay=2.0,
            parameters=[{
                'port': '/dev/k230',
                'baud': 115200,
                'topic': '/detections',
                'frame_id': 'k230_camera',
            }],
        ),
    ])
