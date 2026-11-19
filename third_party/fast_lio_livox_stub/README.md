# livox_ros_driver2 消息桩包（message-only stub）

用途：FAST-LIO2（Ericsii/FAST_LIO_ROS2）的 `CMakeLists.txt` 里 `find_package(livox_ros_driver2 REQUIRED)` 是硬依赖，且源码无条件 `#include <livox_ros_driver2/msg/custom_msg.hpp>`；但本项目**没有 Livox 硬件**，且真驱动在 Jetson 的 GCC 7.5 / PCL 1.8 / CMake 3.27 环境下编译失败（PCL 导出定义含空 `-D`，详见 `docs/FAST-LIO2适配评估.md`）。

因此用这个**同名最小包**替代：只生成 `CustomPoint.msg` / `CustomMsg.msg` 两个消息，不含任何驱动 C++。部署方式：把 `~/ros2_ws/src/livox_ros_driver2` 换成此目录内容（真驱动源码可移到工作区外保留）。

消息文件原样复制自 `Livox-SDK/livox_ros_driver2`（commit `2144554`）的 `msg/` 目录。

编译命令（Jetson 容器内）：

```bash
source /opt/ros/humble/install/setup.bash
cd /root/ros2_ws
colcon build --packages-up-to fast_lio --cmake-args -DDISTRO_ROS=humble --cmake-clean-cache
```

运行阶段：FAST-LIO2 会订阅 Livox CustomMsg 话题（本项目无数据，不影响）；实际输入走通用 PointCloud2 路径（`lidar_type=4`）。
