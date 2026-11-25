"""手柄遥控启动。

两种接法，用 source 参数切换：

  ros2 launch termite_bringup teleop.launch.py                  # 默认 js
  ros2 launch termite_bringup teleop.launch.py source:=board    # 走控制板固件

  source:=js     手柄接收器插 Jetson 的 USB 口，linux_joy 读 /dev/input/js0
  source:=board  手柄接收器插 RRC-M4 的 USB HOST 口，订阅 /ros_robot_controller/joy

只启动遥控链路，不动底盘驱动。底盘已在跑（robot.launch.py）时直接发 /cmd_vel 即可。
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _make_nodes(context):
    source = LaunchConfiguration('source').perform(context)
    share = get_package_share_directory('termite_bringup')
    params_file = os.path.join(share, 'config', 'teleop.yaml')

    nodes = []
    if source == 'js':
        nodes.append(Node(
            package='termite_bringup',
            executable='linux_joy',
            name='linux_joy',
            parameters=[params_file],
            output='screen',
            respawn=True,
            respawn_delay=2.0,
        ))
        joy_topic = '/joy'
    else:
        joy_topic = '/ros_robot_controller/joy'

    nodes.append(Node(
        package='termite_bringup',
        executable='joy_teleop',
        name='joy_teleop',
        # 文件里的 joy_topic 是 /joy，board 模式下用字典覆盖
        parameters=[params_file, {'joy_topic': joy_topic}],
        output='screen',
        respawn=True,
        respawn_delay=2.0,
    ))
    return nodes


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'source', default_value='js',
            description='js = 手柄插 Jetson；board = 手柄插控制板 USB HOST'),
        OpaqueFunction(function=_make_nodes),
    ])
