#!/bin/bash
# T2.4：在 termite_ros2 容器内启动 EKF + 静态 TF
# 前置：ros_robot_controller、controller odom_publisher 已在跑
set -e
source /opt/ros/humble/install/setup.bash
source /root/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=42

# 静态 TF：base_footprint -> base_link（odom_publisher 的 TF 被注释，需补齐）
pkill -f 'static_transform_publisher' 2>/dev/null || true
nohup ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 base_footprint base_link \
  > /tmp/tf_base.log 2>&1 &
sleep 1
# IMU 坐标系挂到车上（imu_raw.frame_id = imu_link）
nohup ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 base_link imu_link \
  > /tmp/tf_imu.log 2>&1 &
sleep 1

# EKF：/odom_raw + /ros_robot_controller/imu_raw -> /odom + TF odom->base_footprint
pkill -f 'ekf_node' 2>/dev/null || true
CONFIG=/root/ros2_ws/src/config/ekf_local.yaml
[ -f "$CONFIG" ] || CONFIG=/root/ros2_ws/config/ekf_local.yaml
nohup ros2 run robot_localization ekf_node --ros-args --params-file "$CONFIG" \
  > /tmp/ekf.log 2>&1 &
sleep 5
echo "=== EKF 日志 ==="
head -30 /tmp/ekf.log
echo "=== 话题 ==="
ros2 topic list | grep -E '^/odom|/imu_raw' | head
echo "=== /odom 频率 ==="
timeout -s INT 7 ros2 topic hz /odom 2>/dev/null | grep -m2 'average rate' || echo '(无消息)'
echo "=== TF odom->base_footprint ==="
timeout 5 ros2 run tf2_ros tf2_echo odom base_footprint 2>/dev/null | head -15 || echo '(无 TF)'
