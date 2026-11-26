import os


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


P = '/sdcard/termite/detector.py'
try:
    print('SIZE', os.stat(P)[6])
except Exception as e:
    print('NOFILE', e)
    raise SystemExit

f = open(P)
src = f.read()
f.close()
print('TEXTLEN', len(src))
print('CRCLF', '0x%04X' % crc16(src.encode()))

b = open(P, 'rb').read()
print('BYTES', len(b), 'CRCR', '0x%04X' % crc16(b))
print('HEAD', repr(b[:40]))
