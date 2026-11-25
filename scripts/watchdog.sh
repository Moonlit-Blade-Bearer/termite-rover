#!/usr/bin/env bash
# 宿主机看门狗（systemd timer 每 2 分钟调用一次）：
#   1) 容器没跑 → docker start
#   2) /odom 连续 3 次无数据 → docker restart（对付"进程活着但 ROS 卡死"）
set -u

C=termite_ros2
STATE=/var/lib/termite-watchdog.fail
ROS='source /opt/ros/humble/install/setup.bash && source /root/ros2_ws/install/setup.bash && export ROS_DOMAIN_ID=42'

log() { logger -t termite-watchdog "$*"; }

if ! docker inspect -f '{{.State.Running}}' "$C" 2>/dev/null | grep -q true; then
  log "容器未运行，执行 docker start"
  docker start "$C" >/dev/null 2>&1
  echo 0 > "$STATE"
  exit 0
fi

# 控制板没插（/dev/rrc 不存在）时，/odom 必然没有，重启容器也没用，跳过
if [ ! -e /dev/rrc ]; then
  log "控制板 /dev/rrc 未就绪，跳过心跳检查"
  echo 0 > "$STATE"
  exit 0
fi

if docker exec "$C" bash -lc "$ROS && timeout 8 ros2 topic hz /odom 2>/dev/null | grep -q average"; then
  echo 0 > "$STATE"
  exit 0
fi

n=$(cat "$STATE" 2>/dev/null || echo 0)
n=$((n + 1))
echo "$n" > "$STATE"
log "/odom 无数据（连续 $n 次）"

if [ "$n" -ge 3 ]; then
  log "连续 3 次无数据，重启容器"
  docker restart "$C" >/dev/null 2>&1
  echo 0 > "$STATE"
fi
