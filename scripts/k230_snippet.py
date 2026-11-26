import os

print('BEFORE', os.listdir('/sdcard'))
try:
    os.rename('/sdcard/main.py', '/sdcard/main.py.hiwonder')
    print('RENAMED OK')
except Exception as e:
    print('RENAME ERR', e)
print('AFTER', os.listdir('/sdcard'))
