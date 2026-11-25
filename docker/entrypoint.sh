#!/usr/bin/env bash
# 容器入口：补齐补丁 → 等串口 → 启动建图栈。
# 该进程是容器 PID 1（exec），launch 挂掉容器就退出，由 restart: unless-stopped 拉起。
# 注意：不能开 set -u，ROS 的 setup.bash 会引用未定义的 COLCON_TRACE。
set -o pipefail

source /opt/ros/humble/install/setup.bash
source /root/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

bash /root/docker/fixes.sh

# 开机时 udev 可能还没建好 /dev/rrc 软链，最多等 30s
for _ in $(seq 1 30); do
  [ -e /dev/rrc ] && break
  sleep 1
done
[ -e /dev/rrc ] || echo "[entrypoint] 警告：/dev/rrc 未就绪，驱动会自行重试"

echo "[entrypoint] 启动 termite_bringup/mapping.launch.py"
exec ros2 launch termite_bringup mapping.launch.py
