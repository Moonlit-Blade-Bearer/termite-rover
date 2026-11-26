"""建图栈：基础栈 + RPLIDAR A1 + slam_toolbox（online async）。

用法：
  ros2 launch termite_bringup mapping.launch.py
  ros2 launch termite_bringup mapping.launch.py lidar_port:=/dev/ttyUSB0
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

LIDAR_BY_ID = (
    '/dev/serial/by-id/'
    'usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0'
)


def generate_launch_description():
    share = get_package_share_directory('termite_bringup')
    slam_params = os.path.join(share, 'config', 'slam_toolbox.yaml')
    lidar_port = LaunchConfiguration('lidar_port')

    return LaunchDescription([
        DeclareLaunchArgument(
            'lidar_port',
            default_value=LIDAR_BY_ID,
            description='RPLIDAR A1 串口（默认用 by-id，防 ttyUSB 枚举漂移）',
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(share, 'launch', 'robot.launch.py')
            )
        ),
        Node(
            package='rplidar_ros',
            executable='rplidar_node',
            name='rplidar_node',
            parameters=[{
                'serial_port': lidar_port,
                'serial_baudrate': 115200,
                'frame_id': 'laser',
                'inverted': False,
                'angle_compensate': True,
                'scan_mode': 'Standard',
            }],
            output='screen',
            respawn=True,
            respawn_delay=3.0,
        ),
        Node(
            package='slam_toolbox',
            executable='async_slam_toolbox_node',
            name='slam_toolbox',
            parameters=[slam_params],
            output='screen',
            respawn=True,
            respawn_delay=3.0,
        ),
        # K230 视觉接收：K230 未接/未启动时只会重连，不影响建图
        Node(
            package='termite_bringup',
            executable='vision_receiver',
            name='vision_receiver',
            parameters=[{'port': '/dev/k230', 'frame_id': 'k230_camera'}],
            output='screen',
            respawn=True,
            respawn_delay=3.0,
        ),
        # 毫米波白蚁检测：配置雷达并每 1.28s 推理一次
        Node(
            package='termite_bringup',
            executable='termite_detector',
            name='termite_detector',
            parameters=[{'configure_radar': True, 'stride': 128}],
            output='screen',
            respawn=True,
            respawn_delay=3.0,
        ),
    ])
