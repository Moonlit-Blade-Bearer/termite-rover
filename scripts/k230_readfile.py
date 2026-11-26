#!/usr/bin/env python3
"""读取 K230 上某个示例/文件的内容。"""
import sys
import time

import serial

port = '/dev/ttyACM1'
path = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 2000

s = serial.Serial(port, 115200, timeout=0.2)
s.dtr = True
s.rts = True

end = time.time() + 12
ready = False
while time.time() < end and not ready:
    s.write(b'\x03')
    time.sleep(0.4)
    data = s.read(8192)
    if data and b'>>>' in data:
        ready = True
s.write(b'\r')
time.sleep(0.3)
s.read(8192)

src = 'f=open(%r)\nprint(f.read(%d))\nf.close()' % (path, n)
s.reset_input_buffer()
s.write(('exec(' + repr(src) + ')\r').encode())
time.sleep(2.0)
print(s.read(131072).decode(errors='replace'))
s.close()
