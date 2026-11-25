# termite-rover 主控镜像：在 dustynv ROS2 Humble 基础上补齐运行时依赖与非持久补丁
# 构建：docker build -t termite-ros:humble-l4t-r32.7.1 ~/termite-rover/docker
FROM dustynv/ros:humble-ros-base-l4t-r32.7.1

# 基础镜像里带了一个已过期的 ROS apt 源（GPG EXPKEYSIG），会拖垮 apt-get update。
# 本镜像的 ROS 是预编译在 /opt/ros/humble/install 的，不需要这个源，直接移除。
RUN rm -f /etc/apt/sources.list.d/ros2.list

# 运行时依赖：
#   libgeographic17          robot_localization (EKF) 的 libGeographic.so.17
#   libboost-system/serial    slam_toolbox 链接的 boost 1.65
#   libtbb2                   slam_toolbox 的 TBB
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libgeographic17 \
      libboost-system1.65.1 \
      libboost-serialization1.65.1 \
      libboost-thread1.65.1 \
      libtbb2 \
      libceres1 \
      libgoogle-glog0v5 \
 && rm -rf /var/lib/apt/lists/*

# pyserial：ros_robot_controller 驱动依赖，基础镜像没有。
# 优先官方源，失败再走清华镜像；都失败也不阻塞构建（entrypoint 会用 vendor wheel 兜底）。
RUN pip3 install --no-cache-dir pyserial==3.5 \
 || pip3 install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple pyserial==3.5 \
 || true

# 非持久补丁：rclcpp 头文件（GCC7 optional<variant> 转换）
COPY fixes.sh /tmp/fixes.sh
RUN bash /tmp/fixes.sh && rm -f /tmp/fixes.sh
