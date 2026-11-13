# NOTICE — third_party/hiwonder/JetAcker

本目录为 **幻尔科技官方 JetAcker 仓库** 的源码快照，原样收编、未做任何修改，版权归 Hiwonder Technology Co., Ltd. 所有。收编目的：构建复现不依赖外部网络（GitHub 在本项目环境中访问不稳定）。

- 仓库：https://github.com/Hiwonder/JetAcker
- 分支：`Jetson_Nano`
- 锁定 commit：`80639fd`（快照日期 2026-11-13）
- 收编范围：`ROS2/src/driver/` 全部 6 个包（85 文件，约 0.1MB）
  - `ros_robot_controller` + `ros_robot_controller_msgs` —— RRC-M4 控制板驱动（USB 串口 `/dev/ttyACM0`，包内含 udev 规则）
  - `controller` —— 阿克曼运动学 + `odom_publisher` 节点（发布 `/odom_raw`，Odometry）+ `ekf.yaml`（robot_localization 融合配置）
  - `servo_controller` + `servo_controller_msgs` —— HTS-20H 转向舵机控制
  - `sdk` —— 底层协议 SDK

更新方式：克隆上游仓库对应分支，整目录覆盖本 `driver/` 后更新此 NOTICE 的 commit 与日期。
