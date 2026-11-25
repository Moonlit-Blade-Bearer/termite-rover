#!/bin/bash
# 用合成 Joy 消息验证 joy_teleop 的方向映射，不驱动电机（输出到 /cmd_vel_test）。
# 容器内运行：bash /root/ros2_ws/test_teleop.sh
source /opt/ros/humble/install/setup.bash
source /root/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=42

pkill -f "[l]inux_joy"
sleep 1

run() {
  local axes="$1"
  local label="$2"
  timeout 8 ros2 topic pub -r 20 /joy sensor_msgs/msg/Joy "{axes: $axes}" >/dev/null 2>&1 &
  local pid=$!
  sleep 2
  local lx az
  lx=$(timeout 4 ros2 topic echo /cmd_vel_test --once --field linear.x 2>/dev/null | tr -d '[:space:]')
  az=$(timeout 4 ros2 topic echo /cmd_vel_test --once --field angular.z 2>/dev/null | tr -d '[:space:]')
  printf "%s -> linear.x=%-8s angular.z=%s\n" "$label" "${lx:-N/A}" "${az:-N/A}"
  kill $pid 2>/dev/null
  wait $pid 2>/dev/null
  sleep 0.5
}

run "[0.0,-1.0,0.0,0.0,0.0,-1.0,0.0,0.0]" "左摇杆前推  "
run "[0.0,1.0,0.0,0.0,0.0,-1.0,0.0,0.0]"  "左摇杆后拉  "
run "[0.0,0.0,0.0,1.0,0.0,-1.0,0.0,0.0]"  "右摇杆右推  "
run "[0.0,0.0,0.0,-1.0,0.0,-1.0,0.0,0.0]" "右摇杆左推  "
