# 白蚁探测无人车 —— 执行清单（todo）

> 详细验收标准/验证命令见同目录 `plan.md`；完成一项勾一项；每个里程碑结束建议录一段演示视频 + `ros2 bag` 存档。

## Phase 0：启动（它们可以先做）
- [x] T0.1 本地仓库骨架 + 首提交完成（2026-11-09，5827633，22 文件：README/骨架/docs 四件套/架构图/审计报告/审计脚本）；剩：**org 建空仓 `termite-rover` → remote add + push**
- [x] T0.2 采购清单定稿（盘点完成：白蚁来源 D4 已落实；待补 A8/B1/B3/F1/F5/F6，见 docs/盘点清单.md「盘点结论」）
- [ ] T0.3 上板开发环境：VS Code Remote-SSH 进 Jetson/Pi5 + Foxglove Studio 看话题 + 容器内 colcon helloworld（PC 只留 VMware 备刷机恢复）
- [ ] T0.4 手柄 + 工具到位（PC 上能发 /teleop/cmd_vel）

### Checkpoint A
- [ ] 硬件全部到齐或明确到货时间

## Phase 1：底盘（脊髓）
- [x] T1.1 幻尔控制器上电自检（✅ 用户完成 2026-11-09，舵机/急停正常）
- [ ] T1.2 官方 ROS2 驱动栈（ros_robot_controller + controller）在 **Jetson 容器内**跑通（先完成 T2.1/T2.2）：/odom_raw 30–50Hz
- [ ] T1.3 手柄遥控：10m 往返 ×3 无碰撞，急停 < 0.2s
- [ ] T1.4 里程计标定 + 实测最小转弯半径 R_min，出《标定记录.md》

## Phase 2：Jetson 大脑
- [ ] T2.1 备份官方 18.04 镜像 → 刷 Qengineering Ubuntu 20.04（64GB A1 卡）
- [ ] T2.2 Docker + `dustynv/ros:humble-ros-base-l4t-r32.7.1` + compose.yaml（开机自启）
- [ ] T2.3 幻尔驱动包容器内 colcon build，遥控链路复现
- [ ] T2.4 robot_localization EKF（odom_raw+imu→odom）+ TF 树，rviz 检查贴合无漂移

## Phase 3：建图
- [ ] T3.1 A1 驱动 → /scan 稳定 ≥ 8Hz
- [ ] T3.2 slam_toolbox online_async + mapping.launch.py
- [ ] T3.3 遥控低速绕场建图 ×3 次一致性达标 → map_saver 入库 maps/
- [ ] T3.4 建图全程录包

### Checkpoint B（核心：自主导航闭环）
- [ ] T4.1 AMCL 定位误差达标
- [ ] T4.2 Nav2 阿克曼参数（SmacPlannerHybrid DUBIN + RPP + 关 rotate_to_heading + inflation ≥ R_min×1.2）
- [ ] T4.3 5 航点脚本：10 次目标 ≥ 8 次全自动
- [ ] T4.4 调参笔记 + bag 复现闭环

## Phase 5：视觉（可与 Phase4 并行）
- [ ] T5.1 K230（CanMV）摄像头 + KPU YOLO demo
- [ ] T5.2 帧协议（0x55AA|len|seq|json|crc16）+ Jetson 解析 → /detections；30min 丢帧 < 0.5%
- [ ] T5.3 云台 2 轴 /gimbal_cmd 顺滑 + 限位保护
- [ ] T5.4（可选）深度相机 + RTAB-Map

## Phase 6：超声波补盲
- [ ] T6.1 HC-SR04P 单路 3.3V 验证（玻璃 1.2m 稳定）
- [ ] T6.2 接入 costmap（nav2_range_sensor_layer / 转点云），玻璃绕行实拍
- [ ] T6.3 前向 3 路扇形标定

## Phase 7：机械臂独立（与 3–6 并行）
- [ ] T7.1 Pi5 系统与 ROS2 环境（或 T8.0 版本兼容验证）
- [ ] T7.2 STM32 固件：LX 总线舵机协议 + 限位/急停/堵转保护（2h 无丢包）
- [ ] T7.3 关节控制节点 + IK + 轨插值；拖动示教复现；急停 < 0.5s
- [ ] T7.4 安全姿态序列（断电自由位）

## Phase 8：机械臂并入
- [ ] T8.0（如需）Humble↔Jazzy 通信验证
- [ ] T8.1 Jetson↔Pi5 有线直连 + 静态 IP + multicast 通过；50Hz 不抖
- [ ] T8.2 chrony 对时（offset < 5ms）
- [ ] T8.3 协同任务链：探测点→导航→云台对准→机械臂动作 ×3 全自动

### Checkpoint C（全车协同）
- [ ] 车 + 云台 + 机械臂联合作业演示成功

## Phase 9：白蚁探测（各小块应提前穿插启动）
- [x] T9.0 选型定稿：IWR6843AOPEVM 已到手 + 白蚁来源 D4 已落实（DCA1000EVM：没有 → 暂缓补购，三轮预实验后决定）
- [x] T9.1 采集链路 + 环境箱——✅ 用户已自建 44GB/747 会话数据集（2026-10-18 审计通过）；剩余：Jetson Linux 版 Python 接收器落盘
- [ ] T9.2 信号链：SVD 去静杂波→特征→CNN 已有雏形（厚度回归 MAE 5.3mm/R²0.74）；剩余：STFT 微多普勒谱 + 分类任务解耦（用户 2026-11-09 决定暂缓）
- [x] T9.3 对照实验数据积累——✅ 厚度/湿度/木种网格已铺满（缺格 5 处、深度真值未标、140 会话时钟失效，详见 docs/白蚁数据集审计报告.md）
- [ ] T9.4 检测模型：规则版→轻量CNN；盲测 AUC ≥ 0.85，虚警 ≤ 10%（现有模型实为"板厚计"，白蚁分类指标待会话清洗后测）
- [ ] T9.5 /termite/detection 上车融合

## Phase 10：对齐与融合
- [ ] T10.1 统一时基（Jetson chrony 服务端）
- [ ] T10.2 每条链路延迟标定表（误差 < 20ms）
- [ ] T10.3 ApproximateTimeSynchronizer 融合：对齐帧 ≥ 95%，P95 < 10ms

## Phase 11：CAN 融合与去树莓派
- [ ] T11.1 Jetson CAN up：USB-CAN（首选）或 Waveshare MCP2515 方案
- [ ] T11.2 《CAN 协议.md》：ID 表、心跳、错误码；3 节点 24h 0 错帧
- [ ] T11.3 机械臂 STM32 切 CAN（bxCAN + SN65HVD230），行为与 UART 一致
- [ ] T11.4 幻尔控制器 CAN 能力确认（不行就留 UART，记录决策）
- [ ] T11.5 摘除 Pi5，职责迁 Jetson；24h 稳定性达标
- [ ] T11.6（可选+真实需要）CAN FD

### Checkpoint D（最终架构）
- [ ] 无 Pi5 状态下全功能稳定

## Phase 12：收官
- [ ] T12.1 全链自启 + watchdog + 断电恢复测试
- [ ] T12.2 30 分钟无人值守演示：巡检 → 白蚁探测 → 机械臂作业，成功率 ≥ 90%
- [ ] T12.3 代码/文档提交 GitHub 公开仓库；博客同步 chaihonglei.com；接线表与故障对策归档
