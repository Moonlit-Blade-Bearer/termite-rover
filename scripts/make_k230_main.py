#!/usr/bin/env python3
"""生成 K230 的 main.py：带 CRC 校验，检测器文件损坏就跳过（回 REPL）。

用法：python make_k230_main.py <detector.py> <输出 main.py>
"""
import sys


def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


TEMPLATE = '''# 由 scripts/make_k230_main.py 生成，请勿手改
from hw.start import *
import os

print('$BOOT termite-k230')

P = '/sdcard/termite/detector.py'
EXPECT = 0x%04X


def _crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


try:
    os.stat(P)
    f = open(P)
    src = f.read()
    f.close()
    if _crc16(src.encode()) != EXPECT:
        print('$BOOT_SKIP crc')
    else:
        exec(src)
except Exception as e:
    print('$BOOT_ERR', repr(e))

print('$BOOT_EXIT')
'''


def main():
    src_path, out_path = sys.argv[1], sys.argv[2]
    with open(src_path, 'r', encoding='utf-8') as f:
        src = f.read()
    expect = crc16(src.encode('utf-8'))

    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(TEMPLATE % expect)

    print('detector crc=0x%04X size=%d' % (expect, len(src.encode('utf-8'))))
    print('written', out_path)


if __name__ == '__main__':
    main()
