#!/usr/bin/env python3
"""列出 K230 的 YOLO 示例与 kmodel 模型文件。"""
import sys
import time

import serial

port = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyACM1'


class Repl:
    def __init__(self, port):
        self.s = serial.Serial(port, 115200, timeout=0.2)
        self.s.dtr = True
        self.s.rts = True

    def take_repl(self, timeout=12.0):
        end = time.time() + timeout
        while time.time() < end:
            self.s.write(b'\x03')
            time.sleep(0.4)
            data = self.s.read(8192)
            if data and b'>>>' in data:
                self.s.write(b'\r')
                time.sleep(0.3)
                self.s.read(8192)
                return True
        return False

    def exec(self, src, wait=1.2):
        self.s.reset_input_buffer()
        self.s.write(('exec(' + repr(src) + ')\r').encode())
        time.sleep(wait)
        return self.s.read(65536).decode(errors='replace')


r = Repl(port)
if not r.take_repl():
    print('未能进入 REPL')
    sys.exit(1)

cmds = [
    'import os\nprint("YOLO_EX", os.listdir("/sdcard/examples/20-YOLO-Module-Examples"))',
    'import os\nprint("KMODEL", os.listdir("/sdcard/examples/kmodel"))',
    'import os\nprint("AI_TEST", os.listdir("/sdcard/examples/ai_test_kmodel"))',
    'import os\nprint("HW_SENSOR", os.listdir("/sdcard/hiwonder/sensor"))',
    'import os\nprint("HW_EX", os.listdir("/sdcard/hiwonder/examples"))',
]
for src in cmds:
    print('---')
    print(r.exec(src, 1.5))
r.s.close()
