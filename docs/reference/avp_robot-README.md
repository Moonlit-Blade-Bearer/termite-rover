# avp_robot

园区地下车库「代客泊车（AVP）」无人车平台
基于 Jetson Nano B01 + STM32F407VET6 的阿克曼移动机器人（ROS2），通信架构采用「方案 B 双总线」。

- docs/         设计文档（硬件 / 协议 / 安全 / 里程碑）
- proto/        跨端协议单一来源（Bus-C UART + Bus-F CANFD）
- ros2_ws/      Jetson ROS2 工作空间（colcon）
- firmware/     stm32_control（Bus-C）与 canfd_node（Bus-F）固件
- tools/        CANFD 实验 / 标定 / 录包工具
- scripts/      构建与烧录脚本
- deploy/       开机自启与容器部署

详细方案见《代客泊车AVP无人车_整体方案.md》《代码结构与命名规范.md》。