#!/usr/bin/env python3
"""启动 K230 脚本，并在运行中发送字符，验证 stdin 是否可读。"""
import sys
import time

sys.path.insert(0, '/root/ros2_ws')
from k230_repl import open_port, take_repl  # noqa: E402

src = open('/root/ros2_ws/k230_stdin_test.py').read()

s = open_port()
s, ok = take_repl(s)
if not ok:
    print('未能进入 REPL')
    sys.exit(1)

s.reset_input_buffer()
s.write(('exec(' + repr(src) + ')\r').encode())

time.sleep(3.0)
print('>>> 发送 q')
s.write(b'q')

buf = b''
end = time.time() + 12
while time.time() < end:
    try:
        d = s.read(8192)
    except serial.SerialException:
        print('(串口断开)')
        break
    if d:
        buf += d
print(buf.decode(errors='replace')[-3000:])
s.close()
