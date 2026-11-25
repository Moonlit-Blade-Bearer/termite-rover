# 白蚁探测无人车 —— 执行清单（todo）

> 详细验收标准/验证命令见同目录 `plan.md`；完成一项勾一项；每个里程碑结束建议录一段演示视频 + `ros2 bag` 存档。

## Phase 0：启动（它们可以先做）
- [x] T0.1 ✅ 全部完成（2026-11-09）：公开仓库 https://github.com/Moonlit-Blade-Bearer/termite-rover ，main 已含骨架提交 5827633 + 53c0513
- [x] T0.2 采购清单定稿（盘点完成：白蚁来源 D4 已落实；待下单 A8［选型已定稿 2026-11-11：12V→5V 同步整流 ×2 双轨］/B1/B3/F1/F5/F6，见 docs/盘点清单.md「盘点结论」）
- [ ] T0.3 上板开发环境：VS Code Remote-SSH 进 Jetson/Pi5 + Foxglove Studio 看话题 + 容器内 colcon helloworld（PC 只留 VMware 备刷机恢复）
- [ ] T0.4 手柄 + 工具到位（PC 上能发 /teleop/cmd_vel）

### Checkpoint A
- [ ] 硬件全部到齐或明确到货时间

## Phase 1：底盘（脊髓）
- [x] T1.1 幻尔控制器上电自检（✅ 用户完成 2026-11-09，舵机/急停正常；2026-11-11 用户确认无异常）
- [ ] T1.2 官方 ROS2 驱动栈（ros_robot_controller + controller）在 **Jetson 容器内**跑通（先完成 T2.1/T2.2）：/odom_raw 30–50Hz
- [ ] T1.3 手柄遥控：10m 往返 ×3 无碰撞，急停 < 0.2s
- [ ] T1.4 里程计标定 + 实测最小转弯半径 R_min，出《标定记录.md》

## Phase 2：Jetson 大脑
- [x] T2.1 ✅ L4T 检查完成（2026-11-12）：**R32.7.6 = JetPack 4.6.6（官方最新）→ 免刷机**；r32.7.1 容器可直接跑（同 32.7 线，CUDA 10.2 不变）。下一步 T2.2 起容器
- [x] T2.2 Docker + `dustynv/ros:humble-ros-base-l4t-r32.7.1` + compose.yaml（开机自启）——✅ 初验通过（2026-11-13）：镜像已拉、容器内 `ros2 topic list` 正常（/parameter_events /rosout）；ROS 为源码编译安装于 `/opt/ros/humble/install/`（bash 启动已自动 source）。
  - ✅ **完成（2026-11-25）**：派生镜像 `termite-ros:humble-l4t-r32.7.1`（`docker/Dockerfile`）补齐 libgeographic17 / boost / TBB / ceres / pyserial；容器 `restart: unless-stopped` + `entrypoint.sh` 开机直接起建图栈；串口 `/dev` 全挂 + udev `/dev/rrc` 可见。详见 `docs/系统固化与运维.md`。
- [x] T2.3 幻尔驱动包容器内 colcon build，遥控链路复现——✅ 编译完成（2026-11-17）：官方 JetAcker 仓 commit 80639fd 六包在 `dustynv/ros:humble-ros-base-l4t-r32.7.1` 容器内 colcon build 全过（1min44s，纯警告），`ros2 pkg list` 识别正常；udev 规则 `/dev/rrc` 已装板上（99-rrc.rules，SYMLINK ttyACM0→rrc，MODE 0777）。
  - 🔴 **卡点（2026-11-22）：插错 USB 口**。RRC-M4 板有两个独立 USB 串口（各自一颗 CH9102F）：
    - **USB 串口 1 / UART1**（Type-C，115200）= 烧录 + 调试口。当前接的就是它 → 只能收到固件 `LOG_DEBUG` 文本（`Start...` / `position:-23131` / `duration:23631`，每次开串口复位后打印一次），1M 下全是误码（`00/f8/80`）。
    - **USB 串口 2 / UART3**（1000000）= RRC 协议口，官方 `ros_robot_controller` 驱动要的就是它（`Board(device="/dev/rrc", baudrate=1000000)`）。官方 FAQ 明确建议「通信走串口 2，串口 1 留给烧录」。
  - ✅ **运行时验收通过（2026-11-23 晚，板子已救活，无需换硬件）**：
    - 根因链：① 板上原固件是"总线舵机示教"demo（非 ROS）；② 首刷的 `JETACKER.hex` IMU 上报被注释且**启动时自锁 RDP**，导致刷后静默+SWD 失联；③ 白色原装 ST-Link 个体故障，换 **U盘式 clone（带 RST 脚）** 后 SWD 恢复。
    - 救活关键：用 clone + OpenOCD（`stm32f407ve_custom.cfg` 强制 512KiB），**保持 halt 不让旧固件运行**，`unlock 0 → mass_erase → flash write_image Acker_12V.hex` 一气呵成，独立会话 `verify_image` 通过（109,024 bytes）。
    - 正确固件 = `RosRobotControllerM4_阿克曼_12V.hex`（IMU 上报激活）。协议口 = CH9102 `...3600`（UART3，1M）。
    - 实测：`/ros_robot_controller/imu_raw` ≈19.5Hz、`battery` ≈0.95Hz、**`/odom_raw` ≈42Hz（达标 30–50Hz）**。
    - 完整踩坑/工具链/救活命令见《RRC-M4刷机与解锁排障记录.md》。
- [x] T2.4 robot_localization EKF（odom_raw+imu→odom）+ TF 树，rviz 检查贴合无漂移（官方 controller 包自带 ekf.yaml 可作起点）
  - ✅ **编译通过（2026-11-25）**：`robot_localization`（humble-devel 3.5.5）+ `geographic_msgs` + `diagnostic_updater` + `angles` 源码编译成功。踩坑：① Jetson Nano 内存不足，`ros_filter.cpp` 编译被 OOM kill → 加 3GB swap + `CMAKE_CXX_FLAGS_RELEASE=-O0`（注意 `-O1` 会被 Release 的 `-O3` 覆盖）；② 测试代码与容器 rclcpp API 不兼容 → `-DBUILD_TESTING=OFF`。
  - ✅ **运行时验收（部分）**：EKF 输出 `/odom` ≈30Hz，TF 链 `odom→base_footprint→base_link→imu_link` 完整（Humble 自带 `static_transform_publisher` 只发一次，改用持续发布的 `config/static_tf_pub.py`）。
  - ✅ **完整验收（2026-11-25）**：板子 `...3600` 口接回 Jetson 后，`/ros_robot_controller/imu_raw` ≈19.6Hz、`battery` ≈0.96Hz；单发布者/单订阅者（EKF）；EKF 输出 `/odom` ≈30Hz，TF 链 `odom→base_footprint→base_link→imu_link` 完整。**T2.4 完成**。配置与启动脚本见 `config/`。
  - 经验：Jetson Nano 编译大 C++ 文件必须加 swap + `-DCMAKE_CXX_FLAGS_RELEASE=-O0`（`-O1` 会被 Release 的 `-O3` 覆盖）；测试代码用 `-DBUILD_TESTING=OFF` 跳过；Humble 的 `static_transform_publisher` 只发一次，后启动监听者收不到，改用 `config/static_tf_pub.py` 持续锁存发布。

## Phase 3：建图
- [x] T3.0 手柄遥控链路（2026-11-25）：飞智八爪鱼5 + 2.4G 接收器插 **Jetson** USB 口。内核 xpad 是内置驱动但白名单缺飞智 `37d7:2501`，接口 0（ff/5d/01 = XInput）无人接管 → 用 `new_id` 绑定，已做持久化（`termite-xpad.service` + `99-flydigi-xpad.rules`，热插拔自动生效）。容器内无 `joy` 包，自写 `linux_joy`（读 `/dev/input/jsX` → `/joy`，50Hz）与 `joy_teleop`（`/joy` → `/cmd_vel`，死区 0.08、限速 ±0.15 m/s / ±0.4 rad/s、0.5s 超时归零、可配死手键）。实测 8 轴 11 键：axis1=左摇杆Y（上推=-1）、axis3=右摇杆X（右推=+1），四方向合成消息验证通过（前 +0.15 / 后 -0.15 / 右 -0.4 / 左 +0.4）。启动：`ros2 launch termite_bringup teleop.launch.py source:=js`。
  - 注意：**控制板固件不认该接收器**——插 RRC-M4 的 USB HOST 口时 IMU 正常但 `/ros_robot_controller/joy` 完全无数据（固件只解析幻尔自家手柄报文），故走 Jetson 路线。
- [x] T3.1 A1 驱动 → /scan 稳定输出（2026-11-25）：`rplidar_ros`(ros2 分支) 编译通过，`/dev/serial/by-id/...CP2102...` 稳定口，health OK、固件 1.27，Standard/Express 均 **≈6.7Hz**（A1 在 2kHz 采样下硬件上限，**未达原定 ≥8Hz 指标**，但足以建图；若必须 ≥8Hz 需换雷达或降采样角度数）。
- [x] T3.2 slam_toolbox online_async + mapping.launch.py（2026-11-25）：源码编译成功（humble 分支，裁掉 RViz 插件依赖；补 `interactive_markers`；修 TBB CMake、rclcpp client.hpp GCC7 转换构造、头文件双层目录）。`/map` 已发布（83×69 栅格），TF 树 `map→odom→base_footprint→base_link→{imu_link,laser}` 完整。启动入口：`ros2 launch termite_bringup mapping.launch.py`。
- [ ] T3.3 遥控低速绕场建图 ×3 次一致性达标 → map_saver 入库 maps/（待现场操作：车动起来后地图才会扩展）
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

## Phase 7：机械臂独立（与 3–6 并行）——2026-11-11 改版：ArmPi Ultra 整机方案
- [ ] T7.0 开箱自检：官方 demo——舵机角度读写、深度相机 RGB+深度流、拖动示教→复现（录视频留档）
- [ ] T7.1 ROS2 版本确认（厂家镜像）+ 与 Jetson Humble 同域联调（talker/listener 联通）
- [ ] T7.2 关节控制节点映射 `/arm/joint_cmd` + 深度相机话题并入 M5；急停 < 0.5s（暂不引入 MoveIt2）
- [ ] T7.3 上车固定 + 供电：3S→7.4V/≥5A buck（独立于 5V 双轨）+ 急停按钮联动
- [ ] T7.4 安全姿态序列（断电自由位、收拢位）+ 工作包络表（避开激光/毫米波视场）

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
- [x] T10.1 统一时基（Jetson chrony 服务端）——✅ **2026-11-26 完成**：chrony 替换 timesyncd（Aliyun 主源，Stratum 3，偏差 15µs），`allow 192.168.0.0/24` 对全网段授时，UDP 123 已监听；`entrypoint.sh` 增加开机时间守卫（年份正常才起栈，最多等 60s）。踩坑记录：`maxupdateskew 100` 太严会退回本地时钟；`local stratum 10` 会阻止上游同步。详见 `docs/时间同步.md`。**剩余**：PC 实测慢 12.27s 待配置、Pi5/K230 上线时指向 Jetson。
- [ ] T10.2 每条链路延迟标定表（误差 < 20ms）
- [ ] T10.3 ApproximateTimeSynchronizer 融合：对齐帧 ≥ 95%，P95 < 10ms

## Phase 11：CAN 融合与去树莓派
- [ ] T11.1 Jetson CAN up：USB-CAN（首选）或 Waveshare MCP2515 方案
- [ ] T11.2 《CAN 协议.md》：ID 表、心跳、错误码；3 节点 24h 0 错帧
- [ ] T11.3 F407 板 CAN 节点固件（bxCAN + SN65HVD230/USB-CAN），承担 CAN 网络辅助通道（毫米波/声学等；ArmPi Ultra 臂本身不走此线）
- [x] T11.4 ✅ 定案（2026-11-11）：底盘 RRC-M4 板载无 CAN → **底盘维持 UART**（`ros_robot_controller` ROS2 包），CAN 网络由 USB-CAN/F407 承担
- [ ] T11.5 臂端 Pi5 保留（ArmPi Ultra 自带主控，不摘除）；臂端官方栈随车 24h 稳定性达标
- [ ] T11.6（可选+真实需要）CAN FD

### Checkpoint D（最终架构）
- [ ] 无 Pi5 状态下全功能稳定

## Phase 12：收官
- [x] T12.1 全链自启 + watchdog + 断电恢复测试
  - ✅ **自启 + 看门狗（2026-11-25）**：统一启动包 `ros2_ws/src/termite_bringup`（`robot.launch.py` / `mapping.launch.py`，全部节点 `respawn=True`）；容器 entrypoint 自动起栈；宿主 `termite-watchdog.timer` 每 2 分钟查容器与 `/odom_raw`，`/dev/rrc` 未接时跳过。实测：容器重建后 entrypoint 自动起栈、雷达崩溃 2s 自动重启、看门狗正确跳过未接硬件。
  - ✅ **看门狗话题名修正（2026-11-26）**：原脚本查 `/odom`（该话题不存在，实际是 `/odom_raw`），硬件接上后每 6 分钟误重启容器一次；已改为 `/odom_raw` 并实测不再误触发。`health.sh` 同步修正。
  - ✅ **断电/重启恢复验收（2026-11-26）**：`sudo reboot` 后 20s SSH 恢复、约 60s 全栈就绪，`health.sh` 全绿：`/scan` 7.09Hz、`/odom_raw` 47Hz、IMU 19.5Hz、`/map` 85×67、`map→base_link` TF 通、容器 healthy；看门狗定时器 02:02 运行无日志（未误重启）；入口时间守卫打印「系统时间正常 2026-11-25 18:00:03 UTC」后才起栈。
- [ ] T12.2 30 分钟无人值守演示：巡检 → 白蚁探测 → 机械臂作业，成功率 ≥ 90%
- [ ] T12.3 代码/文档提交 GitHub 公开仓库；博客同步 chaihonglei.com；接线表与故障对策归档
- [ ] T12.4 下位机固件补丁A：上位机失联 500ms 停电机（2026-11-26 已烧录，待现场验收）
  - 源码：`firmware/rrc-m4-src/`（厂商第16节工程，已打补丁；不入库），补丁：`firmware/patches/0001-host-link-watchdog.patch`、`0002-enable-imu-report.patch`
  - 文档：`docs/固件补丁A-上位机失联看门狗.md`
  - 依据：原厂 ROS 固件无通信超时保护；手柄直控+超时停车的代码在 ROS 版被整段注释
  - ✅ 编译 + 烧录：Keil 0 Error，pyocd 烧写 117760 字节，回读 116904 字节 0 差异；原固件已备份 `firmware/backup/rrc_m4_stock_20261126.bin`
  - ✅ 烧录后验证：IMU 19.7Hz、电池 12.36V、全栈健康
  - ⏳ **待现场**（需轮子转动）：架起车 → 持续发速度 10s 不抖 → 停发指令 0.6s 内停转 → 重发可恢复
