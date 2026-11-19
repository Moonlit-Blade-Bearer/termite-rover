# NOTICE — third_party/FAST-LIO2（官方 upstream，ROS1）

本目录为 **HKU MARS 实验室 FAST-LIO 官方仓库主分支**的源码快照，原样收编、未做修改，版权归原作者所有。

- 仓库：https://github.com/hku-mars/FAST_LIO （**没有独立的 FAST_LIO2 仓库**——README 明确标注 "FAST-LIO 2.0 (2021-07-05 Update)"，本目录就是 FAST-LIO2 本体）
- commit：`7cc4175`（2024-07-23，"Support MARSIM simulator"）
- 依赖：`include/ikd-Tree`（上游子模块 fast_lio 分支，commit `e2e3f4e`）源码已一并收编为普通文件
- 下载日期：2026-11-19；源码以普通文件入库（不含嵌套 .git，避免 gitlink 陷阱），`doc/`（约 128MB）不入库
- 用途：**技术参考**。官方原版基于 ROS1，本项目 ROS2 Humble 请改用隔壁 `third_party/FAST-LIO2-ROS2/`

## 兼容性注意

1. FAST-LIO2 需要 **3D 点云 + IMU**，当前 RPLIDAR A1（2D）不可直接输入。
2. 官方原版为 ROS1；ROS2 上车看 `third_party/FAST-LIO2-ROS2/`。
3. 依赖 livox_ros_driver 自定义消息（非 Livox 雷达需改预处理宏）。
4. 完整适配评估见 `docs/FAST-LIO2适配评估.md`。

更新方式：重新 clone 上游仓库与子模块到临时目录，整目录覆盖本目录（保留 NOTICE.md），再 git add/commit。
