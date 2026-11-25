#!/usr/bin/env bash
# 宿主机一键体检：容器、节点、话题频率、TF 树。
# 用法：~/termite-rover/scripts/health.sh
set -u

C=termite_ros2
ROS='source /opt/ros/humble/install/setup.bash && source /root/ros2_ws/install/setup.bash && export ROS_DOMAIN_ID=42'

echo "=== 容器 ==="
docker ps --filter "name=$C" --format '{{.Names}}  {{.Status}}'

echo "=== 节点 ==="
docker exec "$C" bash -lc "$ROS && timeout 10 ros2 node list" || echo "（取不到节点列表）"

echo "=== 话题频率（各 6s）==="
for t in /scan /odom /ros_robot_controller/imu_raw; do
  printf '%-32s ' "$t"
  docker exec "$C" bash -lc "$ROS && timeout -s INT 6 ros2 topic hz $t 2>/dev/null | grep -m1 average" || echo "无数据"
done

echo "=== /map ==="
docker exec "$C" bash -lc "$ROS && timeout 10 ros2 topic echo /map --once 2>/dev/null | grep -E 'width|height|resolution'" || echo "（无地图）"

echo "=== TF ==="
docker exec "$C" bash -lc "$ROS && timeout 8 ros2 run tf2_ros tf2_echo map base_link 2>/dev/null | grep -m1 'Translation'" || echo "（TF 不通）"
