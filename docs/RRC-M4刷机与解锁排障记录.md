# RRC-M4 控制板刷机与解锁排障记录

> 记录时间：2026-11-22 ~ 2026-11-23
> 最终结论：**板子已救活，T2.3 运行时验收通过，无需换硬件**（见第 9 节）。
> 中途曾误判为 RDP2 锁死/需换板，实为「固件自锁 RDP + 白色 ST-Link 个体故障」叠加，已澄清。

---

## 1. 目标与背景

T2.3 需要验收 `ros_robot_controller` 节点能收到 `/ros_robot_controller/imu_raw`（30–50Hz）和 `battery`（1Hz），
即 Jetson 能通过 RRC 协议口与 STM32 控制板通信（`/dev/rrc`，1Mbps）。

实际现象：驱动节点能启动、话题能挂上，但 **0 条消息**。

---

## 2. 硬件与端口识别

### 2.1 板子
- 幻尔 JetAcker / RRC-M4（板背面丝印 `ROS Robot Controller V1.2`）
- MCU：STM32F407VET6（flash 512KiB，SRAM 192KiB）
- 官方功能分布图上的接口：
  - `USB串口1/烧录下载` —— Type-C（UART1，115200）
  - `USB串口2` —— 4×3 排针（标称 UART3 / 1M 协议口，TTL 电平）
  - `5V5A对外供电` —— Type-C（纯供电）
  - `USB HOST接口` —— Type-A（接手柄接收器）
  - `GPIO扩展及SWD调试` —— 2×12 排针，含 PA13(SWDIO)/PA14(SWCLK)/GND/3.3V

### 2.2 Jetson 上枚举到的 CH9102F（1a86:55d4）
| USB 序列号 | 判断 | 实测 |
|---|---|---|
| `596F003614` | UART1 烧录/调试口 | 旧固件在此输出 `Start...` / `position:-23131` / `duration:23631`（115200） |
| `596F003600` | 另一颗 CH9102 | 全波特率扫描（9600–2M）均 0 字节 |

> udev 规则 `99-rrc.rules` 按序列号 `596F003600` 建 `/dev/rrc` 软链，MODE 0777。
> Docker `compose.yaml` 用 `-v /dev:/dev` 把宿主 /dev 整个挂进容器，解决热插设备与 udev 软链进不去容器的问题。

### 2.3 关键发现：板上固件不是官方版
- 旧固件打印的 `position:` / `duration:` 在资料盘**两个 hex 里都不存在**：
  - `v1.0&v1.1/RosRobotControllerM4_JETACKER.hex`（52,324 B，SHA256 `A8468C7F...49F822A`）
  - `v1.2/RosRobotControllerM4.hex`（65,536 B）
  - 二者内容相同的前者亦等于 `v1.2/RosRobotControllerM4_Acker.hex`
- 结论：板上跑的是第三方/测试固件，不实现 RRC 协议 → 必须刷官方固件。

---

## 3. 工具链（全部已下载安装，PC 端）

| 工具 | 路径 / 版本 | 用途 |
|---|---|---|
| FlyMcu | `G:\学习\百度网盘\大型阿克曼底盘\2.软件工具\01 STM32软件\FlyMcu\FlyMcu.exe` | 官方教程推荐，但 GUI 卡死在 RDP 解除循环，弃用 |
| 官方固件 hex | `C:\Windows\Temp\opencode\JetAcker_FW.hex` | 目标固件（= v1.0/v1.1 JETACKER.hex） |
| 固件 bin | `C:\Windows\Temp\opencode\JetAcker_FW.bin` | 由 hex 转换，52,324 B |
| OpenOCD | `C:\Windows\Temp\opencode\openocd\bin\openocd.exe`（0.12.0，Windows 预编译） | 解锁 RDP + 烧录，主力工具 |
| 自定义 target | `...\share\openocd\scripts\target\stm32f407ve_custom.cfg` | **强制 flash bank 512KiB**（关键！默认会误判成 8193KiB 导致写算法跑飞） |
| stlink 工具 | `C:\Windows\Temp\opencode\stlink\stlink-1.8.0-win32\bin\` | `st-info --probe` 读 chipid / `st-flash` 读写 |
| libusb | `D:\Python3.12\Lib\site-packages\libusb_package\libusb-1.0.dll`（已复制到 stlink bin） | st-flash 运行依赖 |
| stlink 芯片配置 | 已管理员复制到 `C:\Program Files (x86)\stlink\config\chips`（68 个文件） | st-flash 识别 F407 必需 |
| PyOCD | `D:\Python3.12` pip 安装（0.34.3 / 0.46.1） | 不含 F407 target，未能用于烧录 |
| 串口脚本 | `C:\Windows\Temp\opencode\*.py`, `*.sh` | 端口扫描、波特率扫描、RRC 帧探测、bootloader 命令 |

> ⚠️ 以上临时文件在 PC 重启后可能仍在 `C:\Windows\Temp\opencode\`，但 **Jetson 重启后 `/tmp` 脚本会丢失**，需重新 scp。

---

## 4. 诊断与操作时间线

### 4.1 端口排查（11-22 ~ 11-23 上午）
1. 换到第二个口（`...3600`）→ 全波特率 0 字节
2. 直接发 RRC 蜂鸣器/LED 帧 → 无响应、无回包
3. 换到第一个口（`...3614`）→ 同样无数据
4. 结论：两个 USB 口都不是能用的协议口

### 4.2 FlyMcu 烧录失败
- COM12 识别正常，115200 连上 bootloader（读到 BootLoader v3.1、PID 0x413 = STM32F40x/41x）
- 但日志显示死循环：
  ```
  芯片已设置读保护 → 开始去除读保护(全片擦除) → 去除读保护,并擦除成功
  → 重启重连 → 芯片已设置读保护 → 开始去除读保护（卡住）
  ```
- GUI 安装器 InstallAnywhere 卡死（无窗口、CPU≈0），放弃

### 4.3 UART bootloader 直接对话（Python + pyserial）
- 确认命令码：`0x00` Get、`0x01` GetVer+RDP、`0x02` GetID、`0x11` ReadMemory、`0x40` WriteMemory、`0x43` Erase、`0x92` ReadoutUnprotect
- GET 有时 ACK、有时无响应（抽风），GetID/ReadMemory/0x92 全部 NACK
- RDP 状态字节 = `0x00`（已保护）→ 敏感命令被 bootloader 拒绝
- 写了带整体重试的 UART 烧录脚本，仍不稳定，放弃

### 4.4 ST-Link + OpenOCD 解锁与烧录（关键时刻）
ST-Link 接线（20pin → 板子 SWD 排针）：

| ST-Link pin | 信号 | 板子丝印 |
|---|---|---|
| 1（红线端） | VAPP/VTref | 3.3V |
| 7 | SWDIO | PA13 |
| 9 | SWCLK | PA14 |
| 4（或任意偶数） | GND | GND |

- `st-info --probe` 成功：固件 V2J48S7，目标电压 3.23V，chipid `0x413` ✅
- OpenOCD 默认 target 把 flash size 误判为 **8193 KiB**，写算法超时；
  **自制 `stm32f407ve_custom.cfg` 把 flash bank 显式写成 `0x08000000 0x80000` 后解决**
- 选项字节处理：
  - `st-flash --area=option write 0xFFFFFFFF` → 清掉 WRP 写保护，OPTCR 回到 `0x0FFFFFED`
  - `openocd ... -c "stm32f4x unlock 0"` → `stm32f2x unlocked`，OPTCR 变 `0x0FFFAAED`
  - **必须断电重启**让选项字节生效
- 成功烧录命令（最终版）：
  ```powershell
  & "C:\Windows\Temp\opencode\openocd\bin\openocd.exe" `
    -s "C:\Windows\Temp\opencode\openocd\share\openocd\scripts" `
    -f interface/stlink-v2.cfg -f target/stm32f407ve_custom.cfg `
    -c "init" -c "halt" `
    -c "flash write_image C:/Windows/Temp/opencode/JetAcker_FW.bin 0x08000000" `
    -c "exit"
  ```
  输出：`wrote 52324 bytes in 0.67s`
- **独立新会话校验通过**：`verified 52324 bytes in 0.48s`
- st-flash 交叉读回：向量表 `38 7f 01 20 15 03 00 08 ab 4f 00 08 f9 42 00 08`，与 bin 完全一致 ✅

### 4.5 烧录后的致命变化
- 拔掉 ST-Link、把板子 USB 接回 Jetson → 两个口依旧静默，蜂鸣器指令无响应
- 再接回 ST-Link → **chipid=0x000，无法进入 SWD 模式**，OpenOCD `init mode failed`
- 反复重插接线、按复位按钮、ST-Link 重新上电均无效
- 目标电压仍为 3.23V，两个电源灯（PWR / PWR2）常亮，但没有任何用户灯闪烁

---

## 5. 结论与推测

1. **固件确实写进去了并校验通过**（这是已确认的事实）。
2. 烧录后 SWD 与 UART bootloader 同时失效，最可能是：
   - 多次写选项字节过程中误触发 **RDP Level 2**（不可逆，永久禁用调试口和 bootloader）；或
   - 芯片进入某种异常/损坏状态。
3. 因为无法再与芯片通信，**无法进一步验证固件是否在跑，也无法改刷另一个 hex**（`v1.2/RosRobotControllerM4.hex`）。
4. RRC 协议口究竟在 USB 还是 4 针排针，也因芯片失联而无法最终确认。

**T2.3 判定：BLOCKED（硬件故障），需换板/换芯片。**

---

## 6. 换板后的恢复流程（约 10 分钟）

1. 换上新的 RRC-M4 控制板，按第 4.4 节接线图接 ST-Link
2. 确认 `st-info --probe` 能读到 chipid `0x413`
3. **不要动选项字节**（新板出厂 RDP 通常是 Level 0，直接烧录即可）
4. 用 `stm32f407ve_custom.cfg` + OpenOCD 烧 `JetAcker_FW.bin`（命令见 4.4）
5. 独立新会话 `verify_image` 校验
6. 拔 ST-Link，板子 USB 接 Jetson，udev 规则确认 `/dev/rrc`
7. 跑 `bash /tmp/probe_rrc_host.sh`，期望 `aa55_frames > 0`
8. 起 `ros_robot_controller` 节点，`ros2 topic hz /ros_robot_controller/imu_raw` 期望 30–50Hz

> 若新板出厂固件已可用，可跳过第 3–5 步，直接做第 6–8 步验收。

---

## 7. 经验教训（写给未来的自己）

1. **不要轻易写 STM32 选项字节**，尤其用 st-flash 的 `--area=option write`；F4 的 RDP Level 2 不可逆。
2. OpenOCD 的 `verify_image` 在**同一会话**里可能是缓存假象，必须**另起会话独立校验**。
3. OpenOCD 的 F4 target 会误判 flash size；遇到"flash size = 8193 KiB"要显式指定 flash bank。
4. FlyMcu 在 RDP 解除循环时没有超时退出机制，不如 OpenOCD 可控。
5. `privileged: true` 的 Docker 容器只在启动时快照 `/dev`，热插串口必须 `-v /dev:/dev`。
6. 交叉验证很重要：OpenOCD 说成功但 st-flash 读回不一致 → 才发现缓存假象。

---

## 8. 补充发现（`G:\学习\百度网盘\STM32机器人控制器` 资料库，2026-11-23）

这个资料库比 `大型阿克曼底盘` 更全，纠正了两个关键认知：

### 8.1 板上原固件 = 总线舵机"示教"演示，不是 ROS 固件
`3.RosRobot Controller程序分析\第8节 ...\RosRobotControllerM4_serial_servo_teach.hex`
解码后同时含 `Start...` + `position:` + `duration:`，与板上原始打印完全吻合。
→ 这块板出厂跑的是舵机示教 demo，**两个 USB 口本来就不实现 RRC 协议**。之前"插错口"的判断不全面。

### 8.2 之前刷的 JETACKER 固件 IMU 上报被注释（刷错了）
- `JETACKER.hex`（52,324B）：源码里 `packet_transmit(...PACKET_FUNC_IMU...)` 被注释 → 刷成功也不吐 IMU。
- 正确 ROS 固件：`第15/16节 RRC与上位机通信烧录文件\RosRobotControllerM4_阿克曼_12V.hex`（65,536B），
  含 `imu_task` / `IMU_data_ready`（IMU 上报激活）。已转存 `C:\Windows\Temp\opencode\Acker_12V.bin/.hex`。
- 注意：该 hex 解码后头部不是标准向量表（app 可能不在 0x08000000 起始），直接用官方下载器更稳妥。

### 8.3 官方下载器
`附录\软件\USB串口下载\ATK-XISP\ATK-XISP.exe`（比 FlyMcu 可靠）；
另有 `Flash Loader Demonstrator`、`串口助手 amaoComV4.9.exe`。

### 8.4 仍无法恢复的原因
- SWD 死（chipid=0x000），无法用 ST-Link 重刷/验证。
- UART bootloader 进不去（DTR/RTS 各序列 SYNC 偶发 OK 但 GET 无响应）→ 芯片跑应用固件、不接受引导命令。
- 综合判断：RRC 协议口（UART3）很可能在 **4 针「USB串口2」排针**上（TTL 电平），两个 Type-C 都不是它；
  且 SWD/bootloader 均失效，软件路径穷尽。

### 8.5 第二个 ST-Link（U盘式 clone）可用，但发现固件自锁 RDP
- 白色原装 ST-Link 后来失联是**个体故障**；U盘式 clone（10pin，带 RST 脚）能正常读 chipid=0x413。
- 但每次 unlock + 断电后，OPTCR 又回到 `0x0FFFFFED`（RDP=Level 1）→ **应用固件在启动时重新打开读保护**。
- 因此重刷必须在固件运行前（connect under-reset）完成；板上 NRST 未引到排针，仅复位按钮可达，操作困难。
- 正确 ROS 固件应刷 `Acker_12V.hex`（直接烧 hex，勿用自转 bin，双地址记录会转错）。

### 8.6 结论与可选硬件方案（更新）
1. **换整块 RRC-M4 板（¥49）**：最省事，出厂固件可用，直接做 T2.3 验收。⭐推荐
2. **换 STM32F407VET6 芯片（¥8–15）**：需焊接；换上后刷 `Acker_12V` 固件。
3. **买 USB-TTL（CH340/CP2102，¥5–10）接「USB串口2」排针**：若芯片其实还在跑、UART3 在排针上，可绕开 SWD 直接用；
   但若 RDP2 锁死则无效。可先买它做最低成本验证。

---

## 9. 最终救活成功（2026-11-23 晚）—— 无需换硬件

### 9.1 澄清两个误判
- **不是 RDP2 永久锁死**：U盘式 clone ST-Link 能读 chipid=0x413，芯片是活的。白色原装 ST-Link 失联是**个体故障**。
- **不是 UART3 在排针**：UART3 就在第二颗 CH9102（`...3600`）的 Type-C 上。之前静默是因为固件不对/自锁 RDP。

### 9.2 真正的根因
刷入的 `JETACKER.hex` ① IMU 上报被注释、② **启动时重新打开 RDP**。导致每次上电后 SWD 又被锁、擦除报 "device protected"。

### 9.3 救活命令（关键：保持 halt，不让旧固件运行）
```powershell
& "C:\Windows\Temp\opencode\openocd\bin\openocd.exe" `
  -s "C:\Windows\Temp\opencode\openocd\share\openocd\scripts" `
  -f interface/stlink-v2.cfg -f target/stm32f407ve_custom.cfg `
  -c "init" -c "halt" `
  -c "stm32f4x unlock 0" `
  -c "stm32f4x mass_erase 0" `
  -c "flash write_image C:/Windows/Temp/opencode/Acker_12V.hex" `
  -c "exit"
# 输出: unlocked / mass erase complete / wrote 109024 bytes
# 再独立会话: -c "verify_image ...Acker_12V.hex"  → verified 109024 bytes
# 最后: -c "reset run"
```
要点：**unlock 后不要 `reset halt`/断电**（那会让旧固件跑起来重新上锁），直接在 halt 态 mass_erase+write。

### 9.4 验收结果（Jetson，`...3600` 口，1M）
- 波特率扫描 1M 下 `aa55=42`（RRC 帧，`AA 55 07 18`=IMU）
- `/ros_robot_controller/imu_raw` ≈19.5Hz；`battery` ≈0.95Hz
- `controller odom_publisher`（calibrate_params.yaml）→ **`/odom_raw` ≈42Hz（达标 30–50Hz）**
- **T2.3 完成**。下一步 T2.4 EKF。

### 9.5 经验更新
- 固件自锁 RDP 时，重刷必须「halt 态一气呵成」，任何 reset/断电都会让旧固件重新上锁。
- 多备一个调试器很有用：白色原装坏了，clone 救了全场。
- 刷 ROS 固件要选 IMU 上报激活的版本（`阿克曼_12V`），不是 `JETACKER`（IMU 被注释）。
