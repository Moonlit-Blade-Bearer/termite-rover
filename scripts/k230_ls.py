import os

for p in ['/', '/bin', '/data', '/etc', '/sdcard']:
    try:
        print(p, os.listdir(p))
    except Exception as e:
        print(p, 'ERR', e)
