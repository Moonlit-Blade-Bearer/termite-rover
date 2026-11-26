#!/usr/bin/env python3
"""读取 K230 上文件的指定区间，便于分析库代码。"""
import sys

sys.path.insert(0, '/root/ros2_ws')
from k230_repl import open_port, take_repl  # noqa: E402

path = sys.argv[1]
start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
end = int(sys.argv[3]) if len(sys.argv) > 3 else 4000

s = open_port()
s, ok = take_repl(s)
if not ok:
    print('未能进入 REPL')
    sys.exit(1)

src = 'f=open(%r)\nt=f.read()\nprint(t[%d:%d])\nf.close()' % (path, start, end)
s.reset_input_buffer()
s.write(('exec(' + repr(src) + ')\r').encode())
import time
time.sleep(2.0)
print(s.read(200000).decode(errors='replace'))
s.close()
