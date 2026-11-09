# 白蚁探测无人车 —— 实施路线图（Implementation Plan）

> 版本 v1.0（2026-10-18）。依据《无人车白蚁探测系统-技术栈与硬件架构.md》与需求笔记《新建 文本文档.txt》整理，并经联网核实。
> 配套执行清单：`docs/todo.md`（逐项勾选）。
> 命名：里程碑 M0–M12，任务 T 编号依次展开。每个任务给出**验收标准 + 验证方法**，完成一项勾一项。

---

## 0. 总原则

1. **梯次验证**：先把每一层跑通并拿出可演示的结果（遥控车 → 自主导航 → 各传感器 → 集成），再进入融合。
2. **研究型风险尽早启动**：毫米波白蚁探测不确定性最大（需要数据积累和白蚁实验来源），从项目早期就并行启动文献、选型与采集链路。
3. **接口统一话题化**：模块内部可以用 UART/CAN/私有协议，但对外一律收敛为 ROS2 话题/服务/动作，保证后期可替换（去树莓派5 时改动最小）。
4. **每阶段留证据**：每完成一个里程碑，录制一段 `ros2 bag` + 一段演示视频，归档到仓库 `docs/demos/`，方便回溯调试和写博客/论文。

## 1. 联网核实后的关键架构修订（对原文档）

| # | 原方案表述 | 核实结论（2026） | 落地做法 |
| --- | --- | --- | --- |
| 1 | "使用社区 Ubuntu 22.04 镜像跑 ROS2 Humble" | 原版 Jetson Nano 官方最高 JetPack 4.6.x（Ubuntu 18.04）；成熟的 22.04 社区镜像基本没有。**成熟方案 = Qengineering Ubuntu 20.04 镜像（JetPack 4.6.2 + CUDA 10.2） + Docker 运行 `dustynv/ros:humble-ros-base-l4t-r32.7.1`（含 CUDA）**，或 Ubuntu 20.04 上源码编译 Humble | 见 T2.1–T2.3。若预算允许后续换 **Jetson Orin Nano**（Ubuntu 22.04 + 官方 JetPack 5/6，且 40-pin 自带 CAN 引脚 29/31），是"最有性价比的架构级解耦" |
| 2 | "机器人停在固定点，原地旋转/云台扫描，采集 360° 点云构建地图" | **2D 单线激光雷达在固定点只能得到一个环向断面，无法生成平面地图**。建图必须由底盘低速移动完成 | M3 改为"遥控低速绕场建图"；"固定地点"应理解为"固定场地" |
| 3 | "Nav2 中配置阿克曼运动学与最小转弯半径" | Nav2 Humble 原生支持：全局规划用 `nav2_smac_planner` 的 **SmacPlannerHybrid**（DUBIN=只前进 / REEDS-SHEPP=允许倒车，参数 `minimum_turning_radius` 居中）；局部跟踪用 **RegulatedPurePursuitController**（官方明确支持阿克曼，但必须关掉 `use_rotate_to_heading`，车不能原地自转） | 见 T4.2 参数清单 |
| 4 | "超声波接 Jetson GPIO" | 可行（HC-SR04 的 Echo 是 5V，需分压或买 3.3V 兼容的 **HC-SR04P**），但更稳的是接在幻尔控制器板上（MCU 级 µs 计时准确、抗抖动），经串口协议上传 | 先 Jetson GPIO 快速验证，成熟后迁移到幻尔控制器板 |
| 5 | "Jetson CAN/CAN FD" | 原版 Jetson Nano **无原生 CAN 控制器引出**，需 MCP2515(SPI)+设备树修改，或直接用 **USB-CAN 适配器**（最省事，如 CANable/candleLight、创芯 USBCAN 系列）。已有现成参考：`aria-karimi/jetson-nano-waveshare-can`（惠雪智创 RS485/CAN 扩展板 + Ubuntu 20.04 现成镜像，can0@500k） | M11 优先 USB-CAN 方案；CAN FD 仅在真实带宽需求出现时再上 |
| 6 | "毫米波雷达探测白蚁" | 可行性有文献支撑：IEEE Access 2025《Insect Detection Using mm-Waves（微多普勒检测昆虫）》、2024《Low Noise Wireless Sensing in Termite Detection》。但消费者级 24G 模块（LD2410 等）只给"有人/无人"结果，**拿不到原始 IQ/微多普勒谱**，做研究必须选用可输出原始数据的平台（TI IWR6843\FMCW EVM + DCA1000，或 Infineon BGT60TR13C 开发套件；24GHz 穿透介质优于 60GHz） | M9 分层推进 + 声学振动传感作备选通道 |
| 7 | "K230 做视觉 SLAM 前端 / RTAB-Map 视觉+激光融合" | RTAB-Map/Mono-SLAM 需要深度信息，K230 搭配的 RGB 摄像头没有深度，**视觉+激光融合 SLAM 需另购深度相机**（RealSense D435i / Orbbec 等） | 阶段里将"视觉融合 SLAM"标记为可选升级；基础路线中 K230 只当"端侧检测载荷"，激光 SLAM 照旧 |
| 8 | 幻尔 ROS 控制器 | 幻尔（Hiwonder）官方即提供 ROS2 驱动栈（`ros_robot_controller` + `controller` 运动学包）：发布 `/odom_raw`、订阅 `/controller/cmd_vel`（内部做阿克曼解算），并带 IMU/舵机传感器话题，常规还配 `robot_localization` EKF | 直接用官方包，把精省出的时间投给导航与白蚁探测 |
| 9 | 机械臂 STM32 型号未定 | 协作者仓库 `avp_robot`（代客泊车平台）已确立"方案 B 双总线"（Bus-C UART + Bus-F CANFD），CANFD 节点用 **STM32F407VET6**，且 `deploy/` 采用开机自启+容器部署 | 机械臂控制 MCU 对齐 STM32F407VET6（T7.2/T11.3 固件模式可复用）；M2/T12.1 容器部署直接参考其 deploy/。注意：其《整体方案》《协议》《代码结构与命名规范》文档未随 zip 提供，到位后复核 M7/M11 |
| 10 | （原计划 M9 才开始建数据链路） | **用户已自建数据集（2026-10-18 审计，超前完成 T9.1/T9.3 大部分）**：44 GB / 747 会话，覆盖 4 木种 × 11 厚度档(0–50mm) × 3 地点 × 0–60% 湿度；UART 帧率中位 100.00Hz、incomplete 约 0.5%、文件名与元数据厚度 0 冲突；已训练"厚度回归" DepthCNN（1100 测试窗：MAE 5.3mm / R²=0.74，checkpoint val：MAE 6.7mm / R²=0.57）。**硬发现：① 厚度≥45mm 回归系统性坍缩（50mm 预测浅 9.4mm）——与 60GHz 穿木 ~8.5dB/cm 的物理极限吻合；② depth_mm 从未标注（全 -1），现有模型本质是"板厚计"，不是"白蚁深度计"；③ 同条件配对能量检验显示白蚁信号间歇性强（25mm 椴木 +19.4dB 两对一致，但也有格子 ≈0dB 甚至负值）+ 个别"无白蚁"会话噪声爆表(top5 2682 vs 常态 40–110)** | T9.1/T9.3 标记"已被数据集覆盖"，剩余动作集中在：a) 按会话分组的防泄漏数据划分（val 有 26,545 窗 vs 会话仅 747×4，疑用滑窗采样）；b) 把"有/无白蚁分类"从"厚度回归"里解耦成独立任务线；c) 逐个审计异常会话（45mm 噪声例）；d) ≥40mm 厚度切 HB100 X 频段与声学通道。**（2026-11-09：a/b/c 用户决定暂缓，仅保留 d 随 M9 推进）** |

## 2. 目标架构（最终形态）

```text
[Jetson Nano B01]                       ← 大脑：建图/导航/融合/白蚁决策（Docker 运行 ROS2 Humble）
 ├─ USB/UART ──────────────── 幻尔ROS控制器 ← 脊髓：阿克曼运动学、里程计/IMU、云台舵机、（后期超声波）
 ├─ USB ───────────────────── RPLIDAR A1 → /scan（2D 建图+定位主传感器）
 ├─ USB-Serial ────────────── K230(CanMV+KPU) → /detections（JSON 检测帧）＋ 麦克风回传
 ├─ GPIO(3.3V 分压) 或 幻尔板 ─ 超声波 ×N → sensor_msgs/Range → costmap 补盲
 ├─ USB-CAN / Waveshare MCP2515 ─ can0 ─-mechinal-arm STM32（总线舵机机械臂）
 └─ 以太网/WiFi ←→ Pi5(过渡期)：机械臂高阶控制，后期职责并入 Jetson，去掉 Pi5

TF 链：map →(AMCL) odom →(EKF) base_footprint → base_link → laser / camera_gimbal
```

## 3. 代码仓库骨架（建仓即创建）

```text
termite-rover/                      # 建议放入 GitHub org: Moonlit-Blade-Bearer（公开仓库）
├─ docs/                            # 现有两份文档迁入；每里程碑补充一份复盘 md
├─ docker/                          # compose.yaml（挂载串口/网口、自动重启、开机自启）
├─ jetson_ws/src/
│  ├─ rover_bringup/                # 总启动：驱动+TF+参数
│  ├─ rover_nav/                    # Nav2 参数与 launch（Smac Hybrid + RPP）
│  ├─ rover_sensors/                # 超声、毫米波、云台、K230 解析节点
│  └─ termite_detect/               # 白蚁探测推理 + 多源融合决策
├─ pi5_ws/src/arm_control/          # Pi5 侧机械臂节点（过渡期）
├─ firmware/stm32_lx_arm/           # STM32 总线舵机固件（PlatformIO）
├─ maps/                            # map_saver 输出（.pgm/.yaml 入库）
├─ tools/                           # 标定/录包/丢包统计/延迟测量脚本
└─ docs/                           # plan.md + todo.md（勾选进度）
```

---

## 4. 里程碑与任务

### M0 项目启动（1 周）
- **T0.1 建仓与规范**：GitHub org 下建公开仓库，按第 3 节骨架建目录；把现有两份文档迁入 `docs/`；`README` 写明里程碑进度表。
  - 验收：仓库包含骨架与文档；`git log` 出现首个提交；在本机可 `git clone`。
- **T0.2 采购清单定稿**（见第 6 节）：明确必买/已有/可缓买三类，**重点提前问白蚁实验来源与 TI 毫米波方案报价**。
  - 验收：清单表发到自己笔记（或 GitHub Issue），无"待确认"空项。
- **T0.3 上板优先开发环境（已定：不在 PC 装 Linux）**：
  - 日常开发：Windows 侧 VS Code **Remote-SSH** 直连 Jetson / Pi5——终端操作与 colcon 编译全部在板上执行；
  - 可视化：Windows 装 **Foxglove Studio**（原生客户端），Jetson 端跑 `foxglove_bridge`，rviz2 不再必需；
  - 长任务挂 `tmux` 后台，防断网丢会话；
  - 代码纪律：工程一律 `git push` 到仓库（板易摔、卡易坏，仓库是唯一真源），每日 commit；
  - 保留一个 **VMware Ubuntu 虚拟机**，仅用于 Jetson 刷机/设备树深度恢复（Qengineering 镜像本身在 Windows 用 balenaEtcher 烧 SD 卡即可，无需 Linux 主机；只有改 DTB 的恢复场景才需要）；
  - 学习替代：通读 Nav2 官方文档 + 容器内跑通 `demo_nodes_cpp` talker/listener。
  - 验收：Windows 能 SSH 进 Jetson，容器内建 helloworld 包 colcon build 成功，Foxglove 里看到 `/chatter`。
- **T0.4 手柄与工具准备**：罗技 F710 或 Xbox 手柄（Humble 下 `teleop-twist-joy` 可用）、USB 集线器（供电）、杜邦线/面包板、螺丝刀组。
  - 验收：手柄在 PC Humble 下能发 `/teleop/cmd_vel`。

**Checkpoint A（开工即做）**：所有硬件到货齐备 或 明确到货日期。

### M1 底盘"脊髓"层跑通——变成一台可遥控的阿克曼车（1–2 周）

> **上板优先执行序（2026-10-18 修订）**：T1.2 不再依赖 PC 装 ROS2，改在 Jetson 容器内跑。执行顺序调整为：**T2.1（刷机）→ T2.2（容器起）→ T1.1 → T1.2（容器内）→ T1.3 → T1.4**。T1.1 的控制板自检用幻尔官方 Windows 上位机/APP 完成，全程无 ROS 依赖。
- **T1.1 幻尔控制器上电自检**：按官方手册烧/载固件，APP 遥控验证每个舵机方向、电机正反转、编码器计数方向。
  - 验收：轮子前后正确、转向随转向舵机正确、急停立即停。
- **T1.2 官方 ROS2 驱动栈接入（容器内执行）**：控制板 USB 直连 Jetson，在 Humble 容器内装幻尔 `ros_robot_controller` + `controller` 包，发布 `/odom_raw`（`nav_msgs/Odometry`）、`/imu` 等；订阅端发 `/controller/cmd_vel` 时车辆能有效执行。
  - 验收：`ros2 topic hz /odom_raw ≈ 30–50Hz`；`ros2 topic echo /imu` 数值随姿态变化。
- **T1.3 手柄遥控**：PC 上 `teleop-twist-joy` → `remap` 到 `/controller/cmd_vel`，平滑加减速。
  - 验收：10 m 往返 ×3，最大速度限 0.5 m/s，碰撞 0 次；急停 < 0.2 s。
- **T1.4 里程计标定与 TF**：跑直线 5 m、原地最小转弯半径测量（记录 `R_min`，拍摄转弯合影）；配置 `linear/angular_correction_factor`。
  - 验收：里程计 5 m 误差 < 5%；形成 `标定记录.md`（含 R_min、轮距、轴距实测值）。

### M2 大脑上线：Jetson 系统 + ROS2（1–2 周）
> 风险最高的一条链路，务必先备份。
- **T2.1 刷系统**：Qengineering `Jetson-Nano-Ubuntu-20-image`（JetPack 4.6.x，含 CUDA 10.2/OpenCV/PyTorch）烧 64GB A1 卡；记录镜像来源与 md5。**先备份官方 18.04 镜像。**
  - 验收：系统起机、FPS 正常、WiFi/有线可用、`jtop` 正常。
- **T2.2 Docker + Humble 容器**：升级 Docker 后拉 `dustynv/ros:humble-ros-base-l4t-r32.7.1`；写 `docker/compose.yaml`：`--net=host --privileged`、挂载 `/dev/ttyUSB*`/`/dev/ttyTHS*`、`ROS_DOMAIN_ID=42`、自动重启。
  - 验收：容器内 `ros2 topic list` 正常；Jetson 断电重启后栈自动恢复。
- **T2.3 幻尔驱动进容器**：把官方两包源码放 `~/ros2_ws`，容器内 `colcon build`。
  - 验收：跨容器 `ros2 topic echo /odom_raw` 有数据；手柄遥控在 Jetson 链路上复现 T1.3。
- **T2.4 EKF 与 TF 树**：`robot_localization`（EKF：`odom_raw`+`imu` → `/odom`），发布 `odom→base_footprint`；`rover_bringup` 静态 TF 放 `base_link→laser`（占位）。
  - 验收：rviz 中推车，激光点云与地面环境贴合无明显漂移；TF 2 小时无跳变。

### M3 固定场地建图（1 周）【修正：遥控绕场建图】
- **T3.1 A1 驱动**：`rplidar_ros`（ros2 分支）或 `sllidar_ros2`；注意 A1 供电（独立 5V，USB 口电流要足）；`/scan` 帧率 ≥ 8Hz。
  - 验收：rviz 雷达点云清晰、无跳点；`ros2 topic hz /scan` 稳定。
- **T3.2 slam_toolbox 建图包**：`ros-humble-slam-toolbox`，`online_async` 模式，写 `rover_bringup/mapping.launch.py`。
  - 验收：一处参数文件即可切换建图/定位。
- **T3.3 建图实操**：低速（≤0.3 m/s）遥控绕场 2–3 圈；重点覆盖玻璃区、低反光区；`map_saver_cli` 存图并入库 `maps/`。
  - 验收：墙体线无重影/断裂；连续 3 次重建图轮廓一致；标注玻璃区域。
- **T3.4 录包留档**：建图全程 `ros2 bag record`，供离线调参。

### M4 Nav2 自主导航——阿克曼（2–3 周，调参时间黑洞，预留弹性）
- **T4.1 AMCL 定位**：`map_server + amcl`，初始位姿手动设定；扫描.png 检查粒子云收敛。
  - 验收：路标处定位误差 < 0.15 m/10°。
- **T4.2 阿克曼导航参数**（`rover_nav/config/nav2_params.yaml`）：
  - planner_server：`nav2_smac_planner/SmacPlannerHybrid`，`motion_model_for_search: "DUBIN"`（先），`REEDS_SHEPP`（允许倒车后再开），`minimum_turning_radius: <T1.4 实测 R_min>`；
  - controller_server：`nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController`，`use_rotate_to_heading: false`，期望横向控制稳定速度 0.3–0.4 m/s；
  - behavior_server：禁用 spin/回旋恢复，仅允许 stop/backup（开了 RS 后）；
  - costmap：静态层 + 障碍层（/scan）+ 膨胀层（inflation_radius ≥ R_min × 1.2）。
- **T4.3 航点巡检脚本**：5 个航点循环（`NavigateToPose` action），带超时与次数统计。
  - 验收：连续 10 次目标点 ≥ 8 次全程无人工干预，0 次剐蹭。
- **T4.4 录包与回归**：出问题后回放 bag 复现并修复参数，形成《调参笔记.md》。

**Checkpoint B（核心里程碑）**：整车可以"给点就走、走到就停"。

### M5 视觉上云台：K230 + 云台（2 周，可与 M4 并行）
- **T5.1 K230 点屏与 YOLO Demo**：CanMV 固件，跑通摄像头 + KPU 推理示例（本地出检测框）。
  - 验收：检测稳定 10+ FPS（模型依选型），彩色终端出框正确。
- **T5.2 结构化上传协议**（Frame: `0x55 0xAA | len | seq | json{cls,x,y,w,h,conf,ts} | crc16`，USB-CDC/UART 115200–921600 或以太网/UDP 备选）：Jetson 侧解析节点发布 `/detections`。
  - 验收：30 分钟连续运行丢帧 < 0.5%（seq 连续性统计，`tools/drop_check.py`）。
- **T5.3 云台控制**：走幻尔控制器舵机接口，Jetson 发 `/gimbal_cmd`（yaw/pitch 限位），云台带动 K230。
  - 验收：云台从 -60°~60° 全程顺滑；上限位/堵转保护生效。
- **T5.4（可选升级）深度相机 + RTAB-Map**：按开放问题决定。

### M6 超声波补盲（1 周）
- **T6.1 单路验证**：HC-SR04P（3.3V 兼容）接 Jetson GPIO（Echo 分压）或幻尔控制器板；测距 0.35–4 m，误差别超 2%。
  - 验收：对玻璃门 1.2 m 处读数稳定；`ros2 topic echo /range_front`。
- **T6.2 接入 costmap**：`nav_msgs/Range` → `nav2_range_sensor_layer`（或转 PointCloud2 进 obstacles 层）。
  - 验收：实测视频——导航遇玻璃门自动修正绕行。
- **T6.3 多路化**：前向 3 路扇形（视底盘空间），事务角/位置标定入参。

### M7 机械臂独立成型（3–4 周，与 M3–M6 并行，用第二台 PC + Pi5 + STM32 桌面开发）
- **T7.1 Pi5 环境**：Ubuntu 22.04(Raspberry Pi 官方镜像优先) + ROS2 Humble（若发行版受限则用同代 ROS2 Jazzy 并先做 T8.0 兼容验证）。
  - 验收：Pi5 上 `demo_nodes_cpp talker/listener` 正常。
- **T7.2 STM32 固件（PlatformIO）**：半双工controllers TTL 串口 LCD 总线舵机协议（帧头 `0x55 0x55`，115200），实现：多关节角度设置（速度电控）、角度/温度/负载回读、**断电自由位 置、紧急停、过温/堵转保护**。
  - 验收：单关节指令 30 Hz 无丢包 2h；手动堵转 1 s 内保护触发。
- **T7.3 Pi5 端上层**：关节控制节点 `/arm/joint_cmd`（`sensor_msgs/JointState` 或自定义 ServoMsgs），简单几何 IK（3–6 自由度选型定）+ 轨插值（50 Hz）；暂不引入 MoveIt2（额外复杂度，等业务真需要）。
  - 验收：拖动示教（回读关节角存轨迹）→ 复现位置误差视觉上无碰；0.5 s 内急停。
- **T7.4 安全框架**：所有运动上限位表、软启动、断电安全位姿态序列。

### M8 机械臂并入整车（1–2 周）
- **T8.0（若跨版本）ROS2 通信兼容验证**：Humble ↔ Jazzy/其他（同 `ROS_DOMAIN_ID`，接口类型基准消息验证）。
- **T8.1 网络**：Jetson ↔ Pi5 有线直连（千兆）为首选：静态 IP、禁 AP 隔离、`ros2 multicast` 测试；WiFi 作备选。
  - 验收：跨机 `talker/listener` 10 分钟无掉线；`/arm/joint_cmd` 50Hz 不抖。
- **T8.2 时钟同步**：chrony，Jetson 为服务器，Pi5 追齐（offset < 5 ms）。
  - 验收：`chronyc tracking` 稳定输出。
- **T8.3 协同任务链**：决策节点（Behavior Tree 可选）串联：`探测点(A) → NavigateToPose(A) → 云台对准 → 机械臂作业Action`。
  - 验收：演示 3 次全流程，无一次人工接管。

**Checkpoint C（全车协同）**：车 + 云台 + 机械臂联合作业演示成功。

### M9 白蚁探测——毫米波（最高风险，理论上限并行启动，真实收官 6–8 周）
- **T9.0 选型（已完成，2026-10-18）**：D1 = **TI IWR6843AOPEVM**（60GHz AOP，已到手）。
  - 特点：天线集成在封装内、免射频对准，上电即评；出厂演示固件可直接输出点云/能量信息，零采购即可开第一轮对照实验；
  - **DCA1000EVM 状态（2026-10-18 确认：没有）→ 不急于买**：先用出厂 demo + D2 声学 + 新增 HB100 低频雷达通道启动数据积累；原始 ADC 采集板推迟到"三轮预实验后按结果决定补购"；
  - **穿透能力实测基准（文献数据，2026-10-18 查证）**：干燥松木在毫米波段 ≈ 6–9 dB/cm（W 波段实测松木 8.5 dB/cm）；NIST 60.5GHz 实测 45mm 木门穿透损耗 25–40 dB。**结论：50mm 木块 = 单程约 35–45dB，雷达双程 70–90dB，60GHz 直接穿透探测不可行**；商业标杆 Termatrac（约 10GHz 低频微波 + 高灵敏处理）的可靠极限也只有 25–50mm（未处理松木 35mm / 经处理松木及硬木 25mm）；
  - **分层对策（确立）**：① 60GHz AOP → 只打**薄板（≤15mm）+ 近场微动**（贴面 <0.5m）；② 厚木（15–50mm）→ **HB100 10.525GHz 多普勒模块**（¥20–40，实木电杆研究已验证的有效低频方案，原始 IF 可采）；③ 任意厚度保底 → 声学/振动（D2）；
  - 应用形态提示：产品级"厚木探伤"可由机械臂钻孔后插入微型探头（声学/微雷达）——正好解释机械臂在系统里的不可替代用途，也呼应 2026 年 RA-IWFNet 融合论文的 multi-band 思路；
  - 备选通道保留：**压电/声学振动**采集白蚁攀爬/啃咬声发射（便宜、与毫米波融合互补）。
  - 验收：一页《毫米波实验初步记录.md》：型号、连接方式、供电、板面-检测面距离四要素 + 首组"白蚁 vs 空箱"能量曲线。
- **T9.1 采集链路（2 周）**：**✅ 已被用户数据集超前覆盖**（44 GB / 747 会话，UART 采集质量经审计优秀：帧率中位 100.00Hz、incomplete ≈0.5%、原始 bin + 解析 CSV 双份存档，详见 `docs/白蚁数据集审计报告.md`）。剩余目标动作：给 Jetson 写 Linux 版 Python 接收器直接落盘，把 PC 从常驻链路里拿掉；复用/移植用户现有采集脚本时，先把 RFC 时间戳（20000101 共 140 会话）与命名体例统一进控制流。
  - 验收：能完成"采集 1 h → 保存 → 复放一次"闭环，工具脚本入库。
- **T9.2 信号处理链（2 周）**：去均值→相位解卷绕→距离 FFT→多普勒 FFT→**STFT 微多普勒谱**→特征（能量比、谱重心、帧能量等）。
  - 验收：有可见的谱图差异粉就无法识别；输出可视化 MATLAB/Python 脚本入库。
- **T9.3 受控实验（贯穿 4–6 周，从 M6 起持续积累）**：白蚁活动箱 vs 空箱对照组（同环境条件），多天多工况（白天/夜间、不同温度），人工观察时间戳标注（可手机录像对齐）。
  - **厚度矩阵实验（先做，一次出结论）**：松木板 0/5/10/15/30/50mm 六组；以"EVM 贴板 + 板后 2cm 微动小目标（低转速小振动器/旋转纸板）"测插入损耗与微动响应，建立自己的《60GHz 穿木极限表》，并与文献松木 ≈8.5 dB/cm 对标；
  - 湿度是最大干扰变量：湿木衰减显著更大——每个厚度记录"干态/加湿态"两组读数（联动 D3 的温湿度计）。
  - **准备提示**：白蚁来源提前联系（林业所/养蚁社群）；培养条件（温湿度、木块、通风）与安全规范先备好，避免实验周期被资料准备拖死。
- **T9.4 检测模型（2 周）**：规则版先上（能量阈值 + 谱峰检测，可直接行车）；随后轻量 CNN（1D 谱）；包装成 `/termite/detection`（`std_msgs/Header` 打戳 + `confidence` + `location_hint`）。
  - 验收：盲测 10 组（含 3 组对照），ROC-AUC ≥ 0.85，虚警 ≤ 10%，推理时延 < 0.5 s/帧。
- **T9.5 上车**：ROS2 节点接 Jetson，结果进融合决策，与 M8 的任务链打通（白蚁点 → 导航 → 机械臂）。

### M10 三源时间戳对齐与融合（1–2 周）
- **T10.1 统一时区**：Jetson 为 chrony 服务端；K230/Pi5 对齐；无网络时的路径（Jetson 本地晶振）记录漂移率。
- **T10.2 延迟标定脚本**：`tools/latency_probe.py`——每条链路注入可计算事件的延迟测量表（先单路后全链）。
  - 验收：每链路固定延迟表入《延迟标定.md》，误差 < 20 ms。
- **T10.3 对齐融合**：`message_filters::ApproximateTimeSynchronizer`（`/scan`+`/detections`+`/termite/detection`），slop 按 T10.2 结果设定（初值 50 ms）；融合规则先用加权投票，升级 Dempster-Shafer 可选。
  - 验收：ros2 bag 复放，对齐成功帧占比 ≥ 95%，对齐时间差 P95 < 10 ms（日志自动打印）。

### M11 总线融合与去树莓派5（2–3 周）
- **T11.1 Jetson 侧 CAN 启用**：方案 A = USB-CAN（CANable/candleLight；国产创芯 USBCAN-II 也行）**首选**；方案 B = Waveshare RS485/CAN 板（MCP2515）+ `jetson-nano-waveshare-can` Ubuntu 20.04 镜像/DTB 流程 → `can0@500k`。
  - 验收：`candump can0` 与对端互发成功；PM 故障注入测试（拔线重插不丢节点）。
- **T11.2 协议定义**：《CAN 协议.md》：帧 ID 表（底盘/机械臂/云台/状态）、DLC、CRC（CAN 自带 CRC15，上层不用再加）、`/odom`、心跳 10 Hz、错误码规范。
  - 验收：两块 MCU + Jetson 三节点 24 小时共网，0 总线错误帧计数（`ip -s -s link show can0`）。
- **T11.3 机械臂 STM32 直连 CAN**：STM32 弄开 bxCAN + SN65HVD230，移植指令帧（`/arm/joint_cmd` 走 CAN 到 CAN）。
  - 验收：从 Jetson 发指令动作组，与原 UART 链路行为一致。
- **T11.4 幻尔控制器 CAN 化（视硬件能力）**：确认幻尔控制板固件支持 CAN/其 SDK 是否暴露 CAN——**不确定则维持 UART**，理由记录入文档（避免为"全 CAN"伪需求改动稳定链路）。
  - 验收：决策文档一句话结论，留凭证链接（SDK 邮件或手册截图）。
- **T11.5 摘除 Pi5**：其职责（IK/关节调度）迁 Jetson 容器跑；STM32 经 CAN 接收关节指令；编号回流测试。
  - 验收：无 Pi5 状态整 24 h 连续导航 + 机械臂动作，无致命故障；记录 CPU/内存/温度曲线。
- **T11.6 平线检查（可选）**：CAN FD 仅在 M11.2 协议证明带宽瓶颈为真时启用。

**Checkpoint D（最终架构达成）**：Pi5 摘除、三类传感数据融合决策全通。

### M12 整机集成与展示（1–2 周）
- **T12.1 全自启动**：`docker compose`/systemd 装配开机自启 + watchdog（进程级 + 业务级心跳），断电恢复测试。
- **T12.2 完整演示剧本**：上电 → 自检灯/语音（可选）→ 建图/巡检（5 航点）→ 白蚁点探测 → 云台确认 → 机械臂标注/取样 → 巡检报告 JSON（落地消息队列/网页面板可选）。
  - 验收：30 分钟无人值守巡检，成功率 ≥ 90%，事故 0 起。
- **T12.3 对外输出**：代码正式提交 GitHub org（公开仓库、README、视频演示）；文章/博客同步到 chaihonglei.com"作品星球"；整理《图纸接线表.md》《故障与对策.md》。

---

## 5. 关键工期参考（按每周 10–15 小时投入，串行 ≈ 4 个月；可并行项压缩）

| 里程碑 | 工期 | 可否并行 |
| --- | --- | --- |
| M0 启动/采购/学习 | 1 周 | — |
| M1 底盘遥控 | 1–2 周 | — |
| M2 Jetson 环境 | 1–2 周 | 与 M7 并行 |
| M3 建图 | 1 周 | — |
| M4 Nav2 导航 | 2–3 周 | |
| M5 视觉 | 2 周 | 与 M4 并行 |
| M6 超声波 | 1 周 | 与 M4/M5 并行 |
| M7 机械臂独立 | 3–4 周 | **全程与 M3–M6 并行** |
| M8 机械臂并入 | 1–2 周 | — |
| M9 毫米波白蚁 | 6–8 周（含数据积累） | **理论+采集穿插全项目** |
| M10 融合对齐 | 1–2 周 | — |
| M11 CAN 去Pi5 | 2–3 周 | — |
| M12 收官 | 1–2 周 | — |

## 6. 采购清单（BOM，按需增减）

| 类别 | 推荐 | 用途 | 参考价 |
| --- | --- | --- | --- |
| SD 卡 | 64GB A1 ×2（Jetson 主卡+备份卡） | 系统 | ¥150 |
| 散热 | Jetson Nano 专用壳+风扇 | 稳定 | ¥100 |
| 电源 | 5V/8A + 5V/4A 两路 DC-DC（总 10A@5V 预算） | 全车供电 | ¥150 |
| 手柄 | 罗技 F710 / Xbox 无线 | 遥控 | ¥250–400 |
| 超声波 | HC-SR04P（3.3V 兼容）×4 | 补盲 | ¥80 |
| CAN | CANable/candleLight 或 创芯 USBCAN-II，SN65HVD230 ×2 | M11 | ¥150–350 |
| 毫米波（主方案） | ✅ 已到手：TI IWR6843AOPEVM（60GHz AOP）；DCA1000EVM 暂缓购（三轮预实验后决定） | M9 | 主板已投 |
| 厚木雷达通道 | HB100 10.525GHz 多普勒模块 ×2（原始 IF 可采；电线杆研究验证过） | M9 | ¥20–40 |
| 声学备选 | 压电振动传感 ×2 + USB 声卡 | M9 备选/融合 | ¥200 |
| 深度相机（可选） | RealSense D435i（二手）/ Orbbec | 视觉 SLAM | ¥1500–3000 |
| 实验耗材 | 亚克力箱、松木块、温湿度计、湿度喷雾 | M9 | ¥100 |
| 网络附件 | 千兆网线 ×3、网线直连头（RJ45 键线） | M8/M11 | ¥100 |

## 7. 风险与对策（在原文档基础上补充）

| 风险 | 等级 | 对策 |
| --- | --- | --- |
| Jetson Nano B01 软件老旧（JetPack 4.6 / Ubuntu 18.04 官方上限） | 高 | 按已核实的 Qengineering 20.04 + Docker Humble 方案走；若预算允许**换 Orin Nano Super** 一劳永逸（Ubuntu 22.04 + 自带 CAN 引脚），可分两步：先用 Nano 跑通全链，性能够用时再换主板 |
| 固定点旋转不能建 2D 地图（认知误区） | 高 | M3 遥控绕场建图（已写入路线） |
| 毫米波白蚁探测在木料/土壤中的穿透与信噪比 | 高 | 提前做 T9.0 文献评审 + 受控实验先行；准备声学振动备选通道；二者融合提升稳健性 |
| 白蚁实验数据获取时间（来源、饲养、观察） | 高 | M0 即联系来源；培养环境提前准备 |
| 幻尔控制器 CAN 固件未知 | 中 | T11.4 之前先与幻尔确认；不可用则保留 UART，只把机械臂切 CAN |
| Nav2 阿克曼调参费时 | 中 | 参考 T4.2 给出的参数清单；禁回旋恢复；调参进 bag 复现闭环 |
| 丢包/掉帧（文档已列） | 中 | 帧头+长度+seq+CRC16、`tools/drop_check.py` 持续统计、必要时升级物理层（UART→以太网） |
| RTAB-Map 需要深度相机 | 中 | 先只做"检测载荷"；视觉 SLAM 待深度相机到位后再升级 |
| Pi5 ROS2 版本与 Humble 互通 | 低 | 提前做 T8.0 通信验证；必要时机械臂初期暂不跑 ROS |

## 8. 开放问题（2026-10-18 盘点后更新）

**已解决：**
1. ✅ 硬件现状（见 `docs/盘点清单.md`「盘点结论」）：A 组仅缺 A8（DC-DC，不阻塞开工）；B 组缺 B1/B3；C 组全齐；D4 白蚁来源已落实。
2. ✅ D4 白蚁来源已联系——请把渠道/时间/取货安排记入 `docs/`。
3. ✅ D1 毫米波定稿：**TI IWR6843AOPEVM**（60GHz AOP）已到手——免射频对准、上电即评；但单独此板抓不了原始 ADC，微多普勒研究须配 DCA1000EVM（子待办见 T9.0）。

**已解决（续，2026-10-18 晚）：**
4. ✅ **DCA1000EVM：没有** → 延后补购（三轮预实验后按结果决定）；M9 起步 = 出厂 demo + HB100 低频雷达 + D2 声学三通道。
5. ✅ **50mm 穿木（60GHz）：不可行**——干松木 ≈6–9 dB/cm，50mm 单程 35–45dB、双程 70–90dB；Termatrac 商业标杆（~10GHz）可靠极限也只有 25–50mm。分层对策见 T9.0，厚度矩阵实验见 T9.3。

**待确认（回复后更新对应里程碑）：**
6. 幻尔套件具体型号（JetAcker/ROSMASTER/其他）及其控制器固件是否支持 CAN？→ 影响矩阵第 1 条链路的演进方式（T11.4）
7. 底盘电池规格（电压/容量/A 数）？→ 决定 A8 DC-DC 选型（输入范围需覆盖）
8. 机械臂自由度与用途（打孔取样还是指示位？是否承担"厚木钻孔插探头"任务）？→ 决定 C3 舵机数量够不够、是否需要 MoveIt2
9. 是否购入深度相机（B4）做视觉+激光融合 SLAM？→ 决定 RTAB-Map 升级线是否保留
10. 是否考虑中期把 Jetson Nano 换成 Orin Nano（Ubuntu 22.04 官方支持 + 40-pin 自带 CAN 引脚）？→ M2/M11 工作量显著下降的备选，非必选

## 9. 验收总表（_DEFINITION OF DONE_）

- [ ] 遥控车稳定急停（M1）
- [ ] 固定场地 2D 地图入库，可反复重定位（M3）
- [ ] Nav2 10/10 航点成功率（≥8）无剐蹭（M4）
- [ ] 丢帧 < 0.5% 的视觉链路（M5）
- [ ] 玻璃补盲归位绕行实测（M6）
- [ ] 机械臂独立可复现轨迹（M7）
- [ ] 全车协同演示（Checkpoint C）
- [ ] 白蚁探测盲测 ROC-AUC ≥ 0.85 / 虚警 ≤ 10%（M9）
- [ ] 时间戳对齐 P95 < 10 ms（M10）
- [ ] CAN 总线 24 h 无错帧、去树莓派 24h 稳定（M11）
- [ ] 30 min 巡检成功率 ≥ 90%（Checkpoint D/M12）
