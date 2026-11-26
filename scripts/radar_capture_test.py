#!/usr/bin/env python3
"""用数据集同款 cfg 启动 IWR6843，抓 2 秒原始串口流存盘。"""
import time

import serial

CFG = '/root/ros2_ws/radar_dataset.cfg'
OUT = '/root/ros2_ws/radar_live.bin'
CFG_PORT = '/dev/ttyUSB1'
DATA_PORT = '/dev/ttyUSB2'

lines = [l.strip() for l in open(CFG) if l.strip() and not l.strip().startswith('%')]

cfg = serial.Serial(CFG_PORT, 115200, timeout=1.0)
time.sleep(0.3)
cfg.write(b'\r')
time.sleep(0.3)
print('prompt:', repr(cfg.read(256)[-80:]))

for line in lines:
    cfg.write((line + '\r').encode())
    time.sleep(0.08)
    resp = cfg.read(512)
    tail = resp.decode(errors='replace').strip().splitlines()[-1:] if resp else []
    print('%-40s %s' % (line, tail[0][-60:] if tail else ''))
    if line == 'configDataPort 921600 1':
        time.sleep(0.3)

cfg.close()

print('opening data port...')
data = serial.Serial(DATA_PORT, 921600, timeout=0.5)
buf = bytearray()
t0 = time.time()
while time.time() - t0 < 2.0:
    buf += data.read(65536)
data.close()

with open(OUT, 'wb') as f:
    f.write(buf)
print('captured', len(buf), 'bytes ->', OUT)
