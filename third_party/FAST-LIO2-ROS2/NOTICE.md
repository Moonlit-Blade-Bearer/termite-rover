# NOTICE — third_party/FAST-LIO2-ROS2（ROS2 Humble 移植版）

本目录为 **Ericsii/FAST_LIO_ROS2** 的源码快照，原样收编、未做修改，版权归原作者所有。这是 FAST-LIO2 在 ROS2 上的社区移植版，是当前项目链路（ROS2 Humble）真正可编译的版本。

- 仓库：https://github.com/Ericsii/FAST_LIO_ROS2 （默认分支 `ros2`；fork 自 hku-mars/FAST_LIO）
- commit：`2fffc57`（2025-11-17，"fix: #65 Fix typo in add_action for config file"）
- 依赖：`include/ikd-Tree`（hku-mars/ikd-Tree，fast_lio 分支，commit `e2e3f4e`）源码已内联收编
- 下载日期：2026-11-19；普通文件入库（不含嵌套 .git），`doc/`（约 128MB）不入库

## 编译/运行前置（来自上游 README）

- Ubuntu ≥ 20.04、ROS ≥ Foxy（推荐 Humble）、PCL ≥ 1.8、Eigen ≥ 3.3.4；**必须先安装并 source `livox_ros_driver2`**（即使不用 Livox 雷达，CMake 仍依赖它的消息）。
- `colcon build --symlink-install`；运行：`ros2 launch fast_lio mapping.launch.py config_file:=avia.yaml`。
- 参数：`lid_topic` / `imu_topic` / `extrinsic_T` / `extrinsic_R`（雷达相对 IMU 的位姿）、`extrinsic_est_en=false`（外参已知时）、`time_sync_en` 仅在无硬件同步时兜底。
- 通用 PointCloud2 输入为 `lidar_type=4`，**无逐点去畸变**；逐点时间戳对 LIO 精度很重要。
- 本项目的具体适配方案（2D 雷达限制、K230 点云桥接、参数修改清单）见 `docs/FAST-LIO2适配评估.md`。
