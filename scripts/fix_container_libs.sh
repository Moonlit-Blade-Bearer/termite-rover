#!/bin/bash
# 补齐容器里 torch 运行所需的动态库：按报错逐个从宿主 ldconfig 查找并复制到挂载目录。
set -u
DEST="$HOME/ros2_ws/vendor/torch_libs"
ENV="LD_LIBRARY_PATH=/usr/local/cuda-10.2/lib64:/root/ros2_ws/vendor/torch_libs PYTHONPATH=/root/ros2_ws/vendor/torch_pkgs"

for i in $(seq 1 15); do
  out=$(docker exec termite_ros2 bash -lc "$ENV python3 -c 'import torch; print(\"TORCH_OK\", torch.__version__)'" 2>&1)
  last=$(echo "$out" | tail -1)
  echo "[$i] $last"
  if echo "$out" | grep -q TORCH_OK; then
    echo "DONE"
    exit 0
  fi
  lib=$(echo "$out" | grep -oE "[A-Za-z0-9_.+-]+\.so(\.[0-9]+)*: cannot open" | head -1 | sed 's/: cannot open//')
  if [ -z "$lib" ]; then
    echo "UNPARSED"
    echo "$out" | tail -6
    exit 1
  fi
  path=$(ldconfig -p | grep -F " $lib " | awk '{print $NF}' | head -1)
  if [ -z "$path" ]; then
    path=$(find /usr/lib /usr/local/lib /lib -name "$lib" 2>/dev/null | head -1)
  fi
  if [ -z "$path" ]; then
    echo "NOT_FOUND_ON_HOST $lib"
    exit 1
  fi
  echo "    copy $lib <- $path"
  cp -n "$path" "$DEST/"
done
echo "MAX_ITER"
exit 1
