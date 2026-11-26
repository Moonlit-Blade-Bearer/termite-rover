# 由 scripts/make_k230_main.py 生成，请勿手改
from hw.start import *
import os

print('$BOOT termite-k230')

P = '/sdcard/termite/detector.py'
EXPECT = 0xFA66


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
