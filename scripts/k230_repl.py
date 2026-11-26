#!/usr/bin/env python3
"""K230 REPL 客户端（抗 USB 重枚举）。

用法：
  k230_run.py --reset-main         # 把 /sdcard/main.py 改名为 main.py.hiwonder 并重启
  k230_run.py --exec "<code>"      # 在 REPL 里执行一段代码
  k230_run.py --file <path> [n]    # 打印板子上的文件内容
"""
import sys
import time

import serial

PORT = '/dev/k230'
BAUD = 115200


def find_k230():
    """按 USB VID:PID 找 K230 的 CDC 串口（/dev/k230 不存在时的兜底）。"""
    import glob
    import os
    for dev in sorted(glob.glob('/dev/ttyACM*')):
        name = os.path.basename(dev)
        base = os.path.realpath('/sys/class/tty/%s/device' % name)
        p = base
        for _ in range(4):
            vf = os.path.join(p, 'idVendor')
            pf = os.path.join(p, 'idProduct')
            if os.path.exists(vf) and os.path.exists(pf):
                vid = open(vf).read().strip()
                pid = open(pf).read().strip()
                if vid == '1209' and pid == 'abd1':
                    return dev
            p = os.path.dirname(p)
    return None


def open_port(tries=30):
    last = None
    for _ in range(tries):
        port = PORT if __import__('os').path.exists(PORT) else find_k230()
        if not port:
            last = '未找到 K230 串口'
            time.sleep(0.5)
            continue
        try:
            s = serial.Serial(port, BAUD, timeout=0.25)
            s.dtr = True
            s.rts = True
            return s
        except Exception as exc:  # 设备重枚举期间会失败
            last = exc
            time.sleep(0.4)
    raise SystemExit('无法打开 K230 串口: %s' % last)


def read(s, seconds=1.0):
    buf = b''
    end = time.time() + seconds
    while time.time() < end:
        try:
            data = s.read(4096)
        except serial.SerialException:
            return buf, False
        if data:
            buf += data
    return buf, True


def take_repl(s, timeout=15.0):
    end = time.time() + timeout
    while time.time() < end:
        try:
            s.write(b'\x03')
        except serial.SerialException:
            s.close()
            time.sleep(0.8)
            s = open_port()
            continue
        data, alive = read(s, 0.4)
        if b'>>>' in data:
            return s, True
        if not alive:
            s.close()
            time.sleep(0.8)
            s = open_port()
    return s, False


def exec_code(s, src, wait=1.5):
    try:
        s.reset_input_buffer()
        s.write(('exec(' + repr(src) + ')\r').encode())
        time.sleep(wait)
        return s.read(65536).decode(errors='replace')
    except serial.SerialException:
        return '(串口断开)'


def main():
    args = sys.argv[1:]
    s = open_port()
    s, ok = take_repl(s)
    if not ok:
        print('未能进入 REPL')
        return 1

    if args and args[0] == '--reset-main':
        print(exec_code(s, 'import os\n'
                          'if "/sdcard/main.py" in os.listdir("/sdcard"):\n'
                          '    os.rename("/sdcard/main.py", "/sdcard/main.py.hiwonder")\n'
                          'print("MAIN_RENAMED", os.listdir("/sdcard"))', 1.8))
        print(exec_code(s, 'import machine\nmachine.reset()', 0.5))
        s.close()
        print('已重启，等 6 秒...')
        time.sleep(6)
        s = open_port()
        s.write(b'\r')
        data = s.read(8192)
        print('重启后:', data.decode(errors='replace')[:300])
    elif args and args[0] == '--exec':
        print(exec_code(s, args[1], 3.0))
    elif args and args[0] == '--script':
        src = open(args[1], 'r').read()
        wait = float(args[2]) if len(args) > 2 else 3.0
        print(exec_code(s, src, wait))
    elif args and args[0] == '--put':
        local, remote = args[1], args[2]
        content = open(local, 'r', encoding='utf-8').read()
        d = remote.rsplit('/', 1)[0]
        print(exec_code(s, 'import os\ntry:\n os.mkdir(%r)\nexcept Exception:\n pass\nf=open(%r,"w")' % (d, remote), 1.0))
        for i in range(0, len(content), 200):
            chunk = content[i:i + 200]
            s.write(('f.write(' + repr(chunk) + ')\r').encode())
            time.sleep(0.05)
            try:
                s.read(16384)
            except serial.SerialException:
                print('串口断开（第 %d 字节）' % i)
                break
        print(exec_code(s, 'f.close()\nimport os\nprint("PUT_OK", os.stat(%r)[6])' % remote, 1.5))
    elif args and args[0] == '--file':
        n = int(args[2]) if len(args) > 2 else 2000
        src = 'f=open(%r)\nprint(f.read(%d))\nf.close()' % (args[1], n)
        print(exec_code(s, src, 2.5))
    s.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
