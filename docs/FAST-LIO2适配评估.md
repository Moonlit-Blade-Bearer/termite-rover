# FAST-LIO2 适配评估（2026-11-19）

## 0. 结论先行

1. **仓库事实**：没有独立的 `hku-mars/FAST_LIO2` 仓库——FAST-LIO2 就位于官方 `hku-mars/FAST_LIO` 主分支（README 标注 "FAST-LIO 2.0"）。已收编于 `third_party/FAST-LIO2/`（commit `7cc4175`，ROS1 原版，仅作参考）。
2. **ROS2 可编译版**：`third_party/FAST-LIO2-ROS2/`（Ericsii/FAST_LIO_ROS2，commit `2fffc57`，默认分支 `ros2`，最后更新 2025-11-17），这才是我们 ROS2 Humble 链路该用的。
3. **硬件现实**：**RPLIDAR A1（2D 平面雷达）不能直接喂 FAST-LIO2**。算法输入必须是带高度的 3D 点云，且 IMU 与点云需要时间同步。RRC-M4 板载 IMU（`~/imu_raw`）解决了 IMU 一半，但 3D 点云源缺失。
4. **推荐路线**：M3 建图主线走 **2D SLAM（slam_toolbox/Cartographer）+ EKF**，FAST-LIO2 作为 M10 实验分支（用 K230 深度相机制造点云）或未来升级 3D 雷达时启用。详见 §3。

## 1. 为什么 2D 雷达不能直接上 FAST-LIO2（算法层）

| 问题 | 说明 |
| --- | --- |
| 状态维度不可观 | FAST-LIO2 估计 3D 位姿（x,y,z,roll,pitch,yaw）+ 速度 + IMU bias。A1 给出的所有点都在同一平面（z≈0），点对面配准只能约束 x/y/yaw，**z、roll、pitch 无有效观测**——地图退化成"一张纸"，z 轴由 IMU 二次积分主导，几秒就飘。 |
| 去畸变依赖逐点时间戳 | FAST-LIO2 的高精度依赖每个激光点的 `time` 字段做运动补偿；A1 的 `LaserScan` 只有整帧时间戳，`scan→PointCloud2(z=0)` 转换即使能过编译也只是软件冒烟，不能当真建图。 |
| 版本前提 | ROS2 移植版要求 Ubuntu ≥ 20.04、ROS ≥ Foxy、PCL ≥ 1.8、Eigen ≥ 3.3.4，并强制依赖 `livox_ros_driver2` 的消息类型；我们的容器是 **Ubuntu 18.04 用户态**（镜像自带 ROS2 Humble 源码编译环境，Python 3.6.9），存在版本错配风险。**2026-11-19 实测容器内版本**：g++ **7.5.0**（偏旧，但支持 `-std=c++17`，能否编译需实测）、cmake 3.27.9、Eigen 3.3.4（✅ 满足 ≥3.3.4）、**PCL 未安装**（apt 无 libpcl；bionic 源里 `libpcl-dev` 为 1.8.1，满足 ≥1.8，走路线 B 前需 `apt install libpcl-dev`）。 |

> 一句话：**2D 雷达不是"低线数 3D 雷达"**，它是另一种传感器，应该配 2D SLAM 算法；把 LaserScan 硬转成点云是"类型骗过了编译器，物理量骗不过滤波器"。

## 2. 已有硬件能提供的输入

| 数据源 | 现状 | 能否喂 FAST-LIO2 |
| --- | --- | --- |
| RPLIDAR A1 | 2D LaserScan `/scan`（115200 波特率，A1 专用 launch） | ❌ 直接不行；仅可作为 2D SLAM 主线输入 |
| RRC-M4 板载 IMU | `ros_robot_controller` 节点发布 `~/imu_raw`（需配合 `controller` 包 + `/dev/rrc`） | ✅ 可作为 IMU 输入（需标定零偏/外参、时间同步） |
| ArmPi Ultra 上的 K230 深度相机 | 深度图 → 可转 PointCloud2（需内参，FOV 窄） | ⚠️ 可行但挑战大（见 §3 路线 B） |
| 未来 Livox/3D 雷达 | 未采购 | ✅ 标准玩法，效果最好（路线 C） |

## 3. 三条路线（按推荐度排序）

### 路线 A（推荐，零额外成本）：2D SLAM 主线 + EKF

- `/scan`（A1）→ **slam_toolbox**（维护活跃、ROS2 原生，建议）或 **Cartographer**（幻尔底盘官方支持）→ 2D 占用栅格地图；
- T2.4 的 `robot_localization` EKF 融合 `/odom_raw`（开环里程计）+ IMU（`~/imu_raw`）→ `/odom`；
- Nav2 直接用 2D 栅格规划（现有 Nav2 参数：SmacPlannerHybrid + RegulatedPurePursuit 保持可用）；
- FAST-LIO2 源码留在仓库当技术储备，**不动 M3 主线**。

### 路线 B（想真跑 LIO，零购硬件）：K230 深度相机造点云

流程：`K230 深度图 + 内参 → sensor_msgs/PointCloud2 → FAST-LIO2(ROS2) + RRC IMU`。具体调整：

1. **点云桥接节点**（新写，放在 `ros2_ws/src/termite_perception/`）：从深度图反投影到相机坐标系，发布 PointCloud2（保证 `x/y/z` 字段、frame_id 正确）。K230 的 FOV 窄、深度噪声大，需先离线统计噪声模型，滤掉无效深度。
2. **配置**（`config/*.yaml`）：
   - `lid_topic` → K230 点云话题；`imu_topic` → `/ros_robot_controller/imu_raw`（注意节点内是相对名 `~/imu_raw`，需 remap 到全局名）；
   - `lidar_type: 4`（通用 PointCloud2）→ **无逐点去畸变**：把所有点的 `time` 字段置同一值，避免伪时间戳；慢速运动下可接受；
   - `extrinsic_T` / `extrinsic_R` = 相机相对 IMU 的位姿（实测，别拍脑袋）；`extrinsic_est_en: false`；
   - `time_sync_en: false`（先尝试硬件/驱动层同步；没有再兜底开 true）；
   - `blind`、`filter_size_map`、`detect_effective_layer` 按室内场景调；先用 rosbag 离线跑，不要一上来实车。
3. **编译环境（2026-11-19 实测）**：容器内 g++ 7.5.0（偏旧、支持 C++17 但需实测）、cmake 3.27.9、Eigen 3.3.4 ✅；**PCL 未装**——先 `apt update && apt install -y libpcl-dev`（bionic 提供 1.8.1，满足 ≥1.8）；若 GCC 7.5 编不过再考虑换更新基础镜像/工具链（L4T r32.7.6 内核 4.9 跑 22.04 用户态容器可行性待验证，注意别混 deb ROS 包破坏源码编译的 Humble）。
4. **依赖**：即使不用 Livox 也要装 `livox_ros_driver2` 并 source（CMake 层依赖）；或改 CMake 去掉该依赖。
5. **闭环验收**：静态场景点云地图无漂移、z 轴稳定（水平地面 z 变化 < 几 cm）；慢速绕圈回环闭合；再上 Nav2。

### 路线 C（效果最好，等预算）：二手 3D 雷达

二手 Livox MID360（约 ¥1500–2500，视成色）→ 原生 `livox_ros_driver2` CustomMsg + 板载 IMU → FAST-LIO2 标准流程（README 里的 `mapping_mid360` 配置几乎开箱即用）。这是"真正用上 FAST-LIO2"的最短路径，但违背"先不花钱"原则，列为 M10 升级选项。

## 4. 决策与执行顺序

- **现在（M3）**：按路线 A 推进——先做 `/scan` + `odom_raw` + IMU 的 EKF，再上 slam_toolbox 建图；
- **M10 实验（可选）**：若那时 K230 已上车且有点云输出，按路线 B 做 FAST-LIO2 实验分支，成败以 rosbag 回放结果为准；
- **触发升级**：路线 B 实测失败或需要真 3D 地图时，再评估路线 C 采购。

## 5. 实机编译尝试记录（2026-11-19，Jetson Nano B01）

按依赖顺序把所有缺失包源码补齐（ROS2 Humble 源码编译环境**没有**这些 deb 包，只能源码编译）：

| 包 | 来源 | 备注 |
| --- | --- | --- |
| `libpcl-dev` 1.8.1 | Ubuntu bionic apt | ROS apt 源签名过期 → `apt-get install -y --allow-unauthenticated libpcl-dev`；下载约 10 分钟 |
| `pcl_msgs` | `ros-perception/pcl_msgs` 分支 `ros2`（commit `8a925a7`） | 第一轮编译报 `Findpcl_msgs.cmake` 缺失后补的 |
| `pcl_conversions` / `pcl_ros` | `ros-perception/perception_pcl` 分支 `humble`（commit `67a5c2b`） | 第一轮报缺 `pcl_msgs` |
| `livox_ros_driver2` | `Livox-SDK/livox_ros_driver2`（commit `2144554`） | 仓库无 `package.xml`（只有 ROS1/ROS2 两份），需 `cp package_ROS2.xml package.xml`；`3rdparty/` 只有 rapidjson，SDK 不在里面；FAST-LIO2 源码无条件 `#include <livox_ros_driver2/msg/custom_msg.hpp>`，绕不开 |
| `Livox-SDK2` | `Livox-SDK/Livox-SDK2`（commit `c0796f0`） | 第二轮报找不到 `liblivox_lidar_sdk_shared.so` 后补；容器内 `cmake .. && make -j2 && make install && ldconfig`（root 身份免 sudo），另需 apt `libusb-1.0-0-dev` |
| `fast_lio` | `Ericsii/FAST_LIO_ROS2` 分支 `ros2`（commit `2fffc57`） | 目标包 |

命令：容器 `fastlio_build`（`-v ~/ros2_ws:/root/ros2_ws --net host --privileged`），`source /opt/ros/humble/install/setup.bash && cd /root/ros2_ws && colcon build --packages-up-to fast_lio`。

状态：第一轮缺 `pcl_msgs`、第二轮缺 `Livox-SDK2`、第三轮 `livox_ros_driver2` 的 `LIVOX_INTERFACES_INCLUDE_DIRECTORIES`=NOTFOUND——**根因是它 CMakeLists.txt 里 `DISTRO_ROS` 从未赋值**，导致永远走旧分支；解决办法是 colcon 传参 `--cmake-args -DDISTRO_ROS=humble`（不改源码），必要时加 `--cmake-clean-cache`。第四轮 `DISTRO_ROS=humble` 后 CMake 通过，但 C++ 报 `CustomMsg`/`PointCloud` 未定义——**真正的首个错误是 `-D  -DBUILDING_ROS2` 里混入一个空的 `-D`**（来自 `add_definitions(${PCL_DEFINITIONS})` 在 PCL 1.8 + CMake 3.27 下产生坏定义），导致后续类型连锁失败；解法：在板上把 `livox_ros_driver2/CMakeLists.txt` 中两处 `add_definitions(${PCL_DEFINITIONS})` 注释掉后重建。第五轮进行中；GCC 7.5 能否通过 C++17 编译待结果。本记录不涉及 M3 主线的改动。

## 6. 关联文件

- `third_party/FAST-LIO2/NOTICE.md`：官方 FAST-LIO2（ROS1，参考）
- `third_party/FAST-LIO2-ROS2/NOTICE.md`：ROS2 移植版（可编译）
- `docs/plan.md`：M2/T2.4 EKF、M3 建图、M10 融合主线
