import os
import sys

try:
    import hw
    print('HW', hw)
    print('HW_FILE', getattr(hw, '__file__', None))
    print('HW_PATH', getattr(hw, '__path__', None))
    print('HW_DIR', [a for a in dir(hw) if not a.startswith('_')])
except Exception as e:
    print('HW_ERR', repr(e))

for p in ['/bin/preload']:
    try:
        print(p, os.listdir(p))
    except Exception as e:
        print(p, 'ERR', e)

print('FROZEN', [m for m in sys.modules if 'hw' in m][:10])
