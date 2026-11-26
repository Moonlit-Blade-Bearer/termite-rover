#!/usr/bin/env python3
"""在 K230 上跑一个示例脚本若干秒，然后 Ctrl-C 收回 REPL。"""
import sys
import time

sys.path.insert(0, '/root/ros2_ws')
from k230_repl import open_port, take_repl, read  # noqa: E402

path = sys.argv[1]
seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0

s = open_port()
s, ok = take_repl(s)
if not ok:
    print('未能进入 REPL')
    sys.exit(1)

src = 'exec(open(%r).read())' % path
print('>>> RUN', path)
s.reset_input_buffer()
s.write(('exec(' + repr(src) + ')\r').encode())

buf = b''
end = time.time() + seconds
while time.time() < end:
    try:
        data = s.read(8192)
    except serial.SerialException:
        print('(串口断开)')
        break
    if data:
        buf += data

print(buf.decode(errors='replace')[-4000:])

print('>>> Ctrl-C 停止')
try:
    s.write(b'\x03')
except serial.SerialException:
    pass
time.sleep(1.0)
try:
    data = s.read(16384)
    print(data.decode(errors='replace')[-2000:])
except serial.SerialException:
    print('(停止时串口断开)')
s.close()
