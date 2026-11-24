#!/bin/bash
# M3：启动 RPLIDAR A1 + slam_toolbox 2D 建图
# 前置：ros_robot_controller、odom_publisher、EKF（/odom + TF）已运行
set -e
source /opt/ros/humble/install/setup.bash
source /root/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=42

# 雷达（A1：/dev/ttyUSB0, 115200, frame_id=laser）
pkill -f '[r]plidar_node' 2>/dev/null || true
LIDAR_PORT=/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0
nohup ros2 launch rplidar_ros rplidar_a1_launch.py serial_port:="$LIDAR_PORT" \
  > /tmp/lidar.log 2>&1 &
sleep 5
echo "=== 雷达日志 ==="; head -12 /tmp/lidar.log
echo "=== /scan 频率 ==="
timeout -s INT 6 ros2 topic hz /scan 2>/dev/null | grep -m2 'average rate' || echo '(无扫描数据)'

# slam_toolbox（异步在线建图，发布 map->odom）
pkill -f '[a]sync_slam_toolbox_node' 2>/dev/null || true
PARAMS=/root/ros2_ws/install/slam_toolbox/share/slam_toolbox/config/mapper_params_online_async.yaml
nohup ros2 launch slam_toolbox online_async_launch.py use_sim_time:=false \
  slam_params_file:="$PARAMS" > /tmp/slam.log 2>&1 &
sleep 10
echo "=== SLAM 日志 ==="; tail -20 /tmp/slam.log
echo "=== /map 频率 ==="
timeout -s INT 6 ros2 topic hz /map 2>/dev/null | grep -m2 'average rate' || echo '(无地图)'
echo "=== TF map->odom ==="
timeout 6 ros2 run tf2_ros tf2_echo map odom 2>/dev/null | grep -E 'At time|Translation' | head -2 || echo '(无 TF)'
