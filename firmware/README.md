# firmware —— RRC-M4 下位机固件

板上控制器是 STM32F407VET6（幻尔 RosRobotControllerM4），跑 FreeRTOS + USB Host。

## 目录

| 路径 | 是否入库 | 说明 |
| --- | --- | --- |
| `rrc-m4-src/` | ❌ 不入库（约 128MB，见 `.gitignore`） | 厂商《第16节 与上位机通信》工程源码，已打补丁A |
| `patches/` | ✅ 入库 | 相对厂商原版的 unified diff，可在 `rrc-m4-src/` 根目录 `git apply` |

## 源码来源

`G:\学习\百度网盘\STM32机器人控制器\3.RosRobot Controller程序分析\第16节 RRC 与上位机通信接收处理源码分析\第16节 RRC 与上位机通信例程\RosRobotControllerM4-armclang.rar`

解压后即为 `rrc-m4-src/`。

## 补丁列表

| 补丁 | 内容 | 文档 |
| --- | --- | --- |
| `0001-host-link-watchdog.patch` | 上位机 500ms 无合法帧 → 停电机 | `docs/固件补丁A-上位机失联看门狗.md` |

## 重建源码目录

```powershell
# 1) 解压厂商 rar（Windows 自带 tar 可读 rar）
mkdir C:\Windows\Temp\opencode\rrc16
tar -xf "<厂商 rar 路径>" -C C:\Windows\Temp\opencode\rrc16

# 2) 拷到本目录，再打补丁
robocopy C:\Windows\Temp\opencode\rrc16\RosRobotControllerM4-armclang firmware\rrc-m4-src /E
cd firmware\rrc-m4-src
git apply ..\patches\0001-host-link-watchdog.patch
```
