#!/usr/bin/env python3
"""T9.5 毫米波白蚁检测节点。

流程：
    /dev/radar_cfg 配置雷达 → /dev/radar_data 读 921600 流
    → radar_iq 解析/组帧 → 滚动窗口 256 帧
    → 每 128 帧跑一次 CNN（板厚回归） → /termite/detection (std_msgs/String JSON)

设计：
    - 读取线程只做串口 + 解析，保证 100Hz 不丢帧
    - 推理线程独立，窗口快照通过 Queue(maxsize=1) 传递（慢时丢旧窗口）
    - 模型目录默认 /root/ros2_ws/ml（挂载卷），需要 torch
"""
import json
import queue
import sys
import threading
import time
from collections import deque

import numpy as np
import rclpy
import serial
import torch
from rclpy.node import Node
from std_msgs.msg import String

from termite_bringup.radar_iq import FrameAssembler, PacketStreamParser

sys.path.insert(0, '/root/ros2_ws/ml')
import config as C          # noqa: E402
import model                # noqa: E402
import pipeline             # noqa: E402

N_RAW_COL = 160


class TermiteDetector(Node):
    def __init__(self):
        super().__init__('termite_detector')
        self.declare_parameter('cfg_port', '/dev/radar_cfg')
        self.declare_parameter('data_port', '/dev/radar_data')
        self.declare_parameter('cfg_file', '/root/ros2_ws/radar_dataset.cfg')
        self.declare_parameter('ckpt', '/root/ros2_ws/ml/best_full.pth')
        self.declare_parameter('topic', '/termite/detection')
        self.declare_parameter('stride', 128)          # 每 128 帧（1.28s）推理一次
        self.declare_parameter('configure_radar', True)

        self.pub = self.create_publisher(String, self.get_parameter('topic').value, 10)
        self.stride = int(self.get_parameter('stride').value)

        # ---- 模型 ----
        ckpt_path = self.get_parameter('ckpt').value
        ck = torch.load(ckpt_path, map_location='cpu')
        self.net = model.build_model()
        self.net.load_state_dict(ck['model_state'])
        self.net.eval()
        self.stats = (np.asarray(ck['feat_mean'], dtype=np.float32),
                      np.asarray(ck['feat_std'], dtype=np.float32),
                      float(ck['y_mean']), float(ck['y_std']))
        self.get_logger().info('模型已加载：%s（%d 参数）' % (ckpt_path, model.count_params(self.net)))

        # ---- 状态 ----
        self.stop = False
        self.window = deque(maxlen=C.WINDOW_LEN)
        self.frames = 0
        self.windows_done = 0
        self.depth = float('nan')
        self.last_window_time = 0.0
        self.win_queue = queue.Queue(maxsize=1)
        self.lock = threading.Lock()
        self.t0 = time.time()

        # ---- 线程 ----
        self.reader = threading.Thread(target=self._read_loop, daemon=True)
        self.infer = threading.Thread(target=self._infer_loop, daemon=True)
        self.reader.start()
        self.infer.start()
        self.create_timer(5.0, self._report)

    # ---------------- 雷达 ----------------
    def _configure(self):
        cfg_file = self.get_parameter('cfg_file').value
        lines = [l.strip() for l in open(cfg_file)
                 if l.strip() and not l.strip().startswith('%')]
        s = serial.Serial(self.get_parameter('cfg_port').value, 115200, timeout=1.0)
        time.sleep(0.3)
        s.write(b'\r')
        time.sleep(0.3)
        s.read(256)
        for line in lines:
            s.write((line + '\r').encode())
            time.sleep(0.08)
            resp = s.read(512).decode(errors='replace')
            if 'error' in resp.lower():
                self.get_logger().warn('雷达配置报错：%s -> %s' % (line, resp.strip()[-60:]))
            if line == 'configDataPort 921600 1':
                time.sleep(0.3)
        s.close()

    def _read_loop(self):
        if self.get_parameter('configure_radar').value:
            try:
                self._configure()
                self.get_logger().info('雷达已配置')
            except Exception as exc:
                self.get_logger().error('雷达配置失败：%s' % exc)

        parser = None
        assembler = FrameAssembler(antenna_count=4, range_bins=20)
        ser = None

        while not self.stop:
            if ser is None:
                try:
                    ser = serial.Serial(self.get_parameter('data_port').value, 921600, timeout=0.2)
                    ser.reset_input_buffer()
                    parser = PacketStreamParser(range_bins=20)
                    assembler = FrameAssembler(antenna_count=4, range_bins=20)
                    self.get_logger().info('数据口已打开')
                except Exception as exc:
                    self.get_logger().warn('数据口打不开：%s（1s 后重试）' % exc)
                    time.sleep(1.0)
                    continue

            try:
                chunk = ser.read(65536)
            except Exception as exc:
                self.get_logger().warn('读数据口失败：%s' % exc)
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
                continue

            if not chunk:
                continue
            for pkt in parser.feed(chunk):
                frame = assembler.add(pkt)
                if frame is None:
                    continue
                with self.lock:
                    self.frames += 1
                    self.window.append(frame.iq.reshape(-1).astype(np.float32))
                    ready = (len(self.window) == C.WINDOW_LEN
                             and self.frames % self.stride == 0)
                    snapshot = np.array(self.window, dtype=np.float32) if ready else None
                if snapshot is not None:
                    try:
                        self.win_queue.put_nowait(snapshot)
                    except queue.Full:
                        pass

    # ---------------- 推理 ----------------
    def _infer_loop(self):
        while not self.stop:
            try:
                win = self.win_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                depth, times = pipeline.full_pipeline(win, self.net, self.stats, device='cpu')
            except Exception as exc:
                self.get_logger().warn('推理失败：%s' % exc)
                continue
            with self.lock:
                self.depth = float(depth)
                self.windows_done += 1
                self.last_window_time = time.time()
                frames = self.frames
            msg = String()
            msg.data = json.dumps({
                'depth_mm': round(float(depth), 2),
                'valid': True,
                'frames': frames,
                'window': int(C.WINDOW_LEN),
                'infer_ms': round(times['T_total'] * 1000, 1),
            })
            self.pub.publish(msg)

    # ---------------- 诊断 ----------------
    def _report(self):
        el = time.time() - self.t0
        with self.lock:
            self.get_logger().info(
                'frames=%d fps=%.1f windows=%d depth=%.2fmm'
                % (self.frames, self.frames / max(el, 1), self.windows_done, self.depth))

    def destroy_node(self):
        self.stop = True
        super().destroy_node()


def main():
    rclpy.init()
    node = TermiteDetector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
