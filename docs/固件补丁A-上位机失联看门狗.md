# 固件补丁 A：上位机失联看门狗

**目标**：Jetson 崩溃、容器死掉、USB 线脱落时，RRC-M4 不再保持最后一次速度，而是在 500ms 内把四个电机的目标速度清零。

**背景**：原厂 ROS 固件（`第16节 与上位机通信` 架构）里，电机只由串口 `set_motor` 命令驱动，**没有任何通信超时保护**（已核对源码，`Hiwonder/` 下不存在相关 timeout 逻辑）。而原厂固件里现成的“手柄直控 + 队列超时停车”那段代码在 ROS 版里被整段注释掉了（`app_task_entry` 只剩 `osDelay(10000)`）。

**改动**：3 个文件，+40 行。

| 文件 | 改动 |
| --- | --- |
| `Hiwonder/Misc/packet.h` | 声明 `extern volatile uint32_t packet_last_host_rx_tick;` |
| `Hiwonder/Misc/packet.c` | 定义该变量；CRC 校验通过时刷新为 `osKernelGetTickCount()` |
| `Hiwonder/System/app.c` | 空闲循环从 `osDelay(10000)` 改为 20ms 轮询；超过 500ms 无合法帧 → 4 个电机 `set_point = 0` |

补丁文件：`firmware/patches/0001-host-link-watchdog.patch`（可用 `git apply` 打在 `firmware/rrc-m4-src` 根目录）。

## 关键代码

`packet.c`（收到任意合法帧就刷新心跳）：

```c
volatile uint32_t packet_last_host_rx_tick = 0;
...
if(crc == self->frame.data_and_checksum[self->frame.data_length]) {
    packet_last_host_rx_tick = osKernelGetTickCount();
    ...
}
```

`app.c`（看门狗主循环）：

```c
#define HOST_LINK_TIMEOUT_MS   500U
#define HOST_LINK_CHECK_MS      20U

uint8_t motor_locked = 0;

for(;;) {
    if(packet_last_host_rx_tick != 0U) {
        if((osKernelGetTickCount() - packet_last_host_rx_tick) > HOST_LINK_TIMEOUT_MS) {
            if(!motor_locked) {
                for(int i = 0; i < 4; ++i) {
                    motors[i]->pid_controller.set_point = 0.0f;
                }
                motor_locked = 1;
            }
        } else {
            motor_locked = 0;
        }
    }
    osDelay(HOST_LINK_CHECK_MS);
}
```

## 设计取舍

- **只清电机，不动舵机**：转向舵机/云台保持原位，避免失联瞬间猛打方向；电机停转已能防止车辆继续前进。
- **一次性动作**：`motor_locked` 保证失联期间只写一次 0；收到新帧后自动解锁，不需要复位。
- **不误触发的前提**：`odom_publisher` 在有 `cmd_vel` 时会持续下发 `set_motor`（手柄 20Hz、Nav2 约 20Hz）。**如果有节点以低于 2Hz 的频率发速度，会周期性触发**，这一点要记住。
- 没有把 `set_point=0` 换成 `chassis->stop()`，因为阿克曼的 `stop()` 会把转向舵机拉回 500（中位），失联时会突然打角。

## 编译

工程是 Keil MDK（ARMCLANG）工程：

1. 安装 MDK（资料在 `G:\学习\百度网盘\STM32机器人控制器\2.STM32开发基础\第1节 开发环境搭建\MDK536.rar`）+ STM32F4 芯片支持包；
2. 打开 `firmware/rrc-m4-src/MDK-ARM/RosRobotControllerM4.uvprojx`；
3. 首次编译前先运行 `armclang.bat`（把 FreeRTOS 的 GCC port 复制成 RVDS port，脚本内置）；
4. Build → 生成 hex。

> 注意：资料里的 `RosRobotControllerM4.ioc` 可以重新生成代码，但厂商明确警告重新生成会覆盖/打乱他们的代码，**不要用 CubeMX 重新生成**。

## 编译验证（2026-11-26）

在本机 Keil MDK（`C:\Keil_v5`）命令行编译通过：

```powershell
UV4.exe -b firmware\rrc-m4-src\MDK-ARM\RosRobotControllerM4.uvprojx -j0 -o build.log
```

结果：`0 Error(s), 0 Warning(s)`，`Code=114000 RO-data=2816 RW-data=80 ZI-data=98384`。

产物：`firmware/rrc-m4-src/MDK-ARM/RosRobotControllerM4/RosRobotControllerM4.hex`

## 回滚固件

工程输出目录里自带厂商出厂 hex（2025-03-11），按底盘选：

| 文件 | 用途 |
| --- | --- |
| `RosRobotControllerM4_阿克曼_12V.hex` | **本车（JetAcker 阿克曼 12V）** |
| `RosRobotControllerM4_差速_8V.hex` | 差速底盘 |
| `RosRobotControllerM4_麦轮_12V.hex` | 麦轮底盘 |
| `RosRobotControllerM4_大/小履带_*.hex` | 履带底盘 |

烧录失败或行为异常时，直接烧 `RosRobotControllerM4_阿克曼_12V.hex` 即可回到出厂状态。

## 烧录（两种，任选其一）

| 方式 | 需要 | 说明 |
| --- | --- | --- |
| SWD | ST-Link / J-Link 探针 | 最稳，可在线调试；工程里已有 `.jflash` 配置 |
| 串口 ISP | USB 转串口 + BOOT0 拉高 | 资料里带 `mcuisp`，不需要探针；烧完记得把 BOOT0 恢复 |

**烧录前务必备份**：

- 附录里有出厂 hex：`G:\学习\百度网盘\STM32机器人控制器\附录\出厂固件\RosRobotControllerM4.hex`；
- 但它**不一定与板上当前固件完全一致**（板上固件可能更新，含 CAN 等）。如果条件允许，先用 SWD 把整片 Flash 读出来存一份。

## 验收步骤（架起车，轮子悬空）

1. 正常遥控，让轮子转起来并保持；
2. 直接**拔掉 Jetson 到控制板的 USB 线**（或 `docker stop termite_ros2`）；
3. 期望：**≤0.6 秒轮子停转**，且转向舵机不动；
4. 插回线，等节点重新连上，再推摇杆 → 应恢复正常，无需重启板子；
5. 反向测试：正常行驶中不要拔线，确认不会误触发（连续跑 1 分钟不应有停顿）。

## 适用范围与风险

- 补丁基于 `第16节 与上位机通信` 工程（资料里最接近板上 ROS 固件的版本）。
- **不能保证与板上出厂固件逐字节同源**。如果厂商后续给了匹配版本的源码，这 3 处改动可以原样搬过去。
- 烧录有变砖风险，但 STM32F407 的 ROM bootloader 可以通过 BOOT0 + 串口救回，属于可恢复操作。
- 本补丁只解决“上位机失联”一种失效；固件自身死机、舵机卡死、驱动管击穿仍需**断电**兜底（无线急停模块暂缓采购，后续补）。
