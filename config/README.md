# config/ 已迁移

原来的手工启动脚本与参数文件已并入统一启动包，避免两处配置漂移：

| 旧位置 | 新位置 |
| --- | --- |
| `config/ekf_local.yaml` | `ros2_ws/src/termite_bringup/config/ekf_local.yaml` |
| `config/static_tf_pub.py` | `ros2_ws/src/termite_bringup/termite_bringup/static_tf.py` |
| `config/start_ekf.sh` | `ros2 launch termite_bringup robot.launch.py` |
| `config/start_slam.sh` | `ros2 launch termite_bringup mapping.launch.py` |

部署与运维见 `docs/系统固化与运维.md`。
