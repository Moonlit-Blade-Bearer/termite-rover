src = "# 由 scripts/make_k230_main.py 生成，请勿手改\nfrom hw.start import *\nimport os\n\nprint('$BOOT termite-k230')\n\nP = '/sdcard/termite/detector.py'\nEXPECT = 0xFA66\n\n\ndef _crc16(data):\n    crc = 0xFFFF\n    for b in data:\n        crc ^= b << 8\n        for _ in range(8):\n            if crc & 0x8000:\n                crc = ((crc << 1) ^ 0x1021) & 0xFFFF\n            else:\n                crc = (crc << 1) & 0xFFFF\n    return crc\n\n\ntry:\n    os.stat(P)\n    f = open(P)\n    src = f.read()\n    f.close()\n    if _crc16(src.encode()) != EXPECT:\n        print('$BOOT_SKIP crc')\n    else:\n        exec(src)\nexcept Exception as e:\n    print('$BOOT_ERR', repr(e))\n\nprint('$BOOT_EXIT')\n"
f = open('/sdcard/main.py', 'w')
f.write(src)
f.close()
print('WROTE', len(src))
