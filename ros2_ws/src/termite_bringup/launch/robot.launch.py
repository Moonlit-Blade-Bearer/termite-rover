"""基础栈：底盘驱动 + 里程计 + EKF + 静态 TF。

所有节点 respawn=True：单点崩溃 2 秒后自动拉起，由 ros2 launch 负责看护。
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    share = get_package_share_directory('termite_bringup')
    ekf_params = os.path.join(share, 'config', 'ekf_local.yaml')

    return LaunchDescription([
        Node(
            package='ros_robot_controller',
            executable='ros_robot_controller',
            output='screen',
            respawn=True,
            respawn_delay=2.0,
        ),
        Node(
            package='controller',
            executable='odom_publisher',
            output='screen',
            respawn=True,
            respawn_delay=2.0,
        ),
        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_filter_node',
            parameters=[ekf_params],
            output='screen',
            respawn=True,
            respawn_delay=2.0,
        ),
        Node(
            package='termite_bringup',
            executable='static_tf_pub',
            output='screen',
            respawn=True,
            respawn_delay=2.0,
        ),
    ])
