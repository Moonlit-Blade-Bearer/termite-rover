#!/usr/bin/env python3
"""K230 视觉接收节点。

从 /dev/k230（USB CDC）读取检测帧，发布 vision_msgs/Detection2DArray。

K230 端帧格式（ASCII 行）：
    $D,<seq>,<json>,<crc16>\\n
    json = {"w":640,"h":360,"fps":19.1,"d":[["person",x,y,w,h,score], ...]}
    crc16 = CRC-16/CCITT-FALSE(json)

设计要点：
- 串口线程持续读、按行解析；断线自动重连（K230 复位会重枚举）
- CRC 校验失败只计数、不发布
- 检测框坐标归一化到 0..1 再发布，方便下游与分辨率解耦
"""
import json
import threading
import time

import rclpy
import serial
from rclpy.node import Node
from vision_msgs.msg import (
    BoundingBox2D,
    Detection2D,
    Detection2DArray,
    ObjectHypothesis,
    ObjectHypothesisWithPose,
)


def crc16(data):
    """CRC-16/CCITT-FALSE，与 K230 端一致。"""
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


class VisionReceiver(Node):
    def __init__(self):
        super().__init__('vision_receiver')
        self.declare_parameter('port', '/dev/k230')
        self.declare_parameter('baud', 115200)
        self.declare_parameter('topic', '/detections')
        self.declare_parameter('frame_id', 'k230_camera')
        self.declare_parameter('stale_sec', 3.0)

        self.port = self.get_parameter('port').value
        self.baud = int(self.get_parameter('baud').value)
        self.frame_id = self.get_parameter('frame_id').value
        self.stale_sec = float(self.get_parameter('stale_sec').value)

        self.pub = self.create_publisher(Detection2DArray, self.get_parameter('topic').value, 10)

        self.ser = None
        self.buf = b''
        self.stop = False
        self.lock = threading.Lock()

        self.frames = 0
        self.bad_crc = 0
        self.bad_json = 0
        self.dets = 0
        self.last_rx = 0.0

        self.thread = threading.Thread(target=self._reader, daemon=True)
        self.thread.start()

        self.create_timer(5.0, self._report)
        self.create_timer(1.0, self._check_stale)
        self.get_logger().info('vision_receiver: %s @ %d -> %s' % (
            self.port, self.baud, self.get_parameter('topic').value))

    # ---------- 串口线程 ----------
    def _reader(self):
        while not self.stop and rclpy.ok():
            if self.ser is None:
                try:
                    self.ser = serial.Serial(self.port, self.baud, timeout=0.1)
                    self.get_logger().info('串口已打开：%s' % self.port)
                except Exception as exc:
                    self.get_logger().warn('打不开 %s：%s（1s 后重试）' % (self.port, exc),
                                           throttle_duration_sec=10.0)
                    time.sleep(1.0)
                    continue

            try:
                chunk = self.ser.read(4096)
            except Exception as exc:
                self.get_logger().warn('读串口失败：%s（重连）' % exc)
                try:
                    self.ser.close()
                except Exception:
                    pass
                self.ser = None
                time.sleep(0.5)
                continue

            if not chunk:
                continue
            self.buf += chunk
            if len(self.buf) > 65536:          # 防御：异常数据不涨内存
                self.buf = self.buf[-8192:]
            while b'\n' in self.buf:
                line, self.buf = self.buf.split(b'\n', 1)
                try:
                    self._handle(line.strip())
                except Exception as exc:
                    self.get_logger().warn('解析异常：%s' % exc, throttle_duration_sec=5.0)

    def _handle(self, line):
        if line.startswith(b'$READY'):
            self.get_logger().info('K230 检测器就绪')
            return
        if line.startswith(b'$ERR') or line.startswith(b'$STOP'):
            self.get_logger().warn(line.decode(errors='replace'))
            return
        if not line.startswith(b'$D,'):
            return

        # 注意：JSON 内部含逗号，必须从右侧切 CRC，再从左侧切 tag/seq
        try:
            body, crc_hex = line.rsplit(b',', 1)
            _tag, _seq, payload = body.split(b',', 2)
        except ValueError:
            return
        try:
            expect = int(crc_hex, 16)
        except ValueError:
            self.bad_crc += 1
            return
        if crc16(payload) != expect:
            self.bad_crc += 1
            return
        try:
            data = json.loads(payload.decode())
        except Exception:
            self.bad_json += 1
            return

        self.frames += 1
        self.last_rx = time.time()
        self._publish(data)

    def _publish(self, data):
        w = float(data.get('w', 640))
        h = float(data.get('h', 360))
        dets = data.get('d', [])

        msg = Detection2DArray()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id

        with self.lock:
            for item in dets:
                if len(item) < 5:
                    continue
                name = str(item[0])
                x, y, bw, bh = [float(v) for v in item[1:5]]
                score = float(item[5]) if len(item) > 5 else 1.0

                det = Detection2D()
                det.header = msg.header
                box = BoundingBox2D()
                # vision_msgs 的 Pose2D 是 position(x,y) + theta
                box.center.position.x = (x + bw / 2.0) / w
                box.center.position.y = (y + bh / 2.0) / h
                box.center.theta = 0.0
                box.size_x = bw / w
                box.size_y = bh / h
                det.bbox = box

                hyp = ObjectHypothesis()
                hyp.class_id = name
                hyp.score = score
                oh = ObjectHypothesisWithPose()
                oh.hypothesis = hyp
                det.results.append(oh)
                msg.detections.append(det)

            self.dets += len(msg.detections)
            self.pub.publish(msg)

    # ---------- 诊断 ----------
    def _report(self):
        age = time.time() - self.last_rx if self.last_rx else -1
        self.get_logger().info(
            'frames=%d dets=%d bad_crc=%d bad_json=%d last=%.1fs' % (
                self.frames, self.dets, self.bad_crc, self.bad_json, age))

    def _check_stale(self):
        if self.last_rx and (time.time() - self.last_rx) > self.stale_sec:
            self.get_logger().warn('K230 超过 %.1fs 无有效帧' % (time.time() - self.last_rx),
                                   throttle_duration_sec=5.0)

    def destroy_node(self):
        self.stop = True
        try:
            if self.ser is not None:
                self.ser.close()
        except Exception:
            pass
        super().destroy_node()


def main():
    rclpy.init()
    node = VisionReceiver()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
