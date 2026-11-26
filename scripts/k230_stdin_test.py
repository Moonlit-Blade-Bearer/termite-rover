# 测试：脚本运行期间能否从 USB CDC 读取主机发来的字符（用于远程停止/调参）
import sys
import time

print('$TEST READY')

has_select = False
poll = None
try:
    import select
    poll = select.poll()
    poll.register(sys.stdin, select.POLLIN)
    has_select = True
except Exception as e:
    print('$TEST no_select', repr(e))

t0 = time.ticks_ms()
count = 0
while time.ticks_diff(time.ticks_ms(), t0) < 10000:
    if has_select:
        if poll.poll(0):
            ch = sys.stdin.read(1)
            count += 1
            print('$GOT', repr(ch))
    time.sleep_ms(100)

print('$TEST DONE', count, 'chars')
