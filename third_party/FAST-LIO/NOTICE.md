# NOTICE — third_party/FAST-LIO

本目录为 **HKU MARS 实验室 FAST-LIO** 的源码快照，原样收编、未做修改，版权归原作者所有。用途：M3/M10 定位建图线的技术参考与潜在复用素材（用户 2026-11-19 要求预下载）。

- 仓库：https://github.com/hku-mars/FAST_LIO
- commit：`7cc4175`（2024-07-23，"Support MARSIM simulator"）
- 依赖：`include/ikd-Tree`（上游子模块 fast_lio 分支，commit `e2e3f4e`）**源码已一并收编为普通文件**
- 下载日期：2026-11-19；收编方式：源码以普通文件入库（不含嵌套 .git，避免 gitlink 陷阱），`doc/` 不入库（见仓库根 .gitignore）

## 集成前必读的兼容性注意

1. **FAST-LIO 需要 3D 激光雷达 + IMU**；本项目当前的 **RPLIDAR A1 是 2D 雷达**，不能直接喂 FAST-LIO。RRC-M4 底盘板自带 IMU（`~/imu_raw`），但 3D 点云数据源还没定（K230 深度相机可产出点云，或后续换 Livox/3D 雷达）。
2. FAST-LIO 原版基于 **ROS1（Noetic）**；本项目链路是 **ROS2 Humble**。真要上车需要移植（或评估 FAST-LIO2 / ROS2 分支/同类 LIO 方案），不可直接 colcon build。
3. 原版依赖 `livox_ros_driver` 的自定义消息（非 Livox 雷达时需按 README 修改 PCD 预处理宏）。

更新方式：重新 clone 上游仓库与子模块到临时目录，整目录覆盖本目录（保留 NOTICE.md），再 git add/commit。
