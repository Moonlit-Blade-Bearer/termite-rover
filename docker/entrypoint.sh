#!/usr/bin/env bash
# 容器入口：补齐补丁 → 等串口 → 启动建图栈。
# 该进程是容器 PID 1（exec），launch 挂掉容器就退出，由 restart: unless-stopped 拉起。
# 注意：不能开 set -u，ROS 的 setup.bash 会引用未定义的 COLCON_TRACE。
set -o pipefail

source /opt/ros/humble/install/setup.bash
source /root/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

bash /root/docker/fixes.sh

# Jetson 无 RTC 电池：开机瞬间系统时间是 2000-01-01，NTP 要几十秒才校正。
# 不校时直接起节点，rosbag / TF / 传感器时间戳全是错的，所以先等年份正常（最多 60s）。
for _ in $(seq 1 60); do
  year=$(date +%Y)
  [ "$year" -ge 2025 ] && break
  sleep 1
done
if [ "$(date +%Y)" -ge 2025 ]; then
  echo "[entrypoint] 系统时间正常：$(date '+%F %T %Z')"
else
  echo "[entrypoint] 警告：60s 内未完成对时（当前 $(date '+%F %T')），继续启动"
fi

# 开机时 udev 可能还没建好 /dev/rrc 软链，最多等 30s
for _ in $(seq 1 30); do
  [ -e /dev/rrc ] && break
  sleep 1
done
[ -e /dev/rrc ] || echo "[entrypoint] 警告：/dev/rrc 未就绪，驱动会自行重试"

echo "[entrypoint] 启动 termite_bringup/mapping.launch.py"
exec ros2 launch termite_bringup mapping.launch.py
