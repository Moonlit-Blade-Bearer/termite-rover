#!/usr/bin/env bash
# 容器内幂等修复：容器重建后自动补齐所有非持久补丁。
# 由 entrypoint.sh 在每次容器启动时调用，可安全重复执行。
set -u

CLIENT_HPP=/opt/ros/humble/install/include/rclcpp/rclcpp/client.hpp
MARK='std::optional<CallbackInfoVariant>(std::move(value))'

# 1) rclcpp client.hpp：GCC 7 下 optional<variant> 隐式转换编译失败（robot_localization /
#    interactive_markers / slam_toolbox 都会踩到）。只改 get_and_erase_pending_request 内那一处。
if [ -f "$CLIENT_HPP" ] && ! grep -qF "$MARK" "$CLIENT_HPP"; then
  echo "[fixes] 打补丁：rclcpp client.hpp (GCC7 optional<variant>)"
  [ -f "$CLIENT_HPP.bak" ] || cp "$CLIENT_HPP" "$CLIENT_HPP.bak"
  python3 - "$CLIENT_HPP" <<'PY'
import sys

path = sys.argv[1]
src = open(path).read()
anchor = 'get_and_erase_pending_request'
old = '    return value;\n'
new = '    return std::optional<CallbackInfoVariant>(std::move(value));\n'
start = src.index(anchor)
pos = src.index(old, start)
open(path, 'w').write(src[:pos] + new + src[pos + len(old):])
PY
fi

# 2) interactive_markers 安装目录把头文件套了两层（include/interactive_markers/interactive_markers/），
#    用同名软链摊平，避免 slam_toolbox 找不到头文件。
IM_INC=/root/ros2_ws/install/interactive_markers/include/interactive_markers
if [ -d "$IM_INC/interactive_markers" ]; then
  for f in "$IM_INC"/interactive_markers/*.hpp; do
    [ -e "$f" ] || continue
    ln -sf "interactive_markers/$(basename "$f")" "$IM_INC/$(basename "$f")"
  done
fi

# 3) pyserial：基础镜像没有，ros_robot_controller 驱动依赖。优先离线装（vendor 里有 wheel）。
if ! python3 -c 'import serial' 2>/dev/null; then
  echo "[fixes] 安装 pyserial"
  pip3 install --no-index --find-links /root/ros2_ws/vendor pyserial==3.5 >/dev/null 2>&1 \
    || pip3 install pyserial==3.5 >/dev/null 2>&1 \
    || echo "[fixes] 警告：pyserial 安装失败（离线且无网络）"
fi
