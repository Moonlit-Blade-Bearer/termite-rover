# K230 无屏 YOLOv5 测试 v3：
#  - Display.VIRT 驱动 ISP 出帧
#  - 传给 YOLO 的必须是 ulab numpy 数组（to_numpy_ref），不是 Image
#  - 逐帧打印耗时，便于定位卡点
from media.sensor import *
from media.display import *
from media.media import *
from libs.YOLO import YOLOv5

import gc
import os
import time
import machine

KMODEL = '/sdcard/examples/kmodel/fruit_det_yolov5n_320.kmodel'
LABELS = ['apple', 'banana', 'orange']
W, H = 640, 360
N = 10

print('MACHINE', [a for a in dir(machine) if not a.startswith('_')])
print('HAS_WDT', hasattr(machine, 'WDT'))

sensor = None
yolo = None
try:
    sensor = Sensor(fps=30)
    sensor.reset()

    sensor.set_framesize(w=W, h=H, chn=CAM_CHN_ID_0)
    sensor.set_pixformat(Sensor.YUV420SP, chn=CAM_CHN_ID_0)
    info = sensor.bind_info(x=0, y=0, chn=CAM_CHN_ID_0)
    Display.bind_layer(**info, layer=Display.LAYER_VIDEO1)

    sensor.set_framesize(w=W, h=H, chn=CAM_CHN_ID_2)
    sensor.set_pixformat(Sensor.RGBP888, chn=CAM_CHN_ID_2)

    Display.init(Display.VIRT, width=W, height=H, fps=30, to_ide=False)
    sensor.run()
    print('SENSOR OK')

    for i in range(5):
        t = time.time()
        img = sensor.snapshot(chn=CAM_CHN_ID_2)
        print('WARM', i, 'snap_ms', int((time.time() - t) * 1000))

    yolo = YOLOv5(task_type='detect', mode='video', kmodel_path=KMODEL,
                  labels=LABELS, rgb888p_size=[W, H], model_input_size=[320, 320],
                  display_size=[W, H], conf_thresh=0.5, nms_thresh=0.45,
                  max_boxes_num=50, debug_mode=0)
    yolo.config_preprocess()
    print('YOLO OK')

    t0 = time.time()
    n = 0
    hits = 0
    while n < N:
        t = time.time()
        img = sensor.snapshot(chn=CAM_CHN_ID_2)
        t_snap = time.time()
        arr = img.to_numpy_ref()
        res = yolo.run(arr)
        t_run = time.time()
        n += 1
        if res:
            hits += 1
        print('F%d snap_ms=%d run_ms=%d hits=%d' % (
            n, int((t_snap - t) * 1000), int((t_run - t_snap) * 1000), len(res) if res else 0))
        if res:
            print('BOX', res)
        gc.collect()

    dt = time.time() - t0
    print('RESULT fps=%.1f frames=%d hits=%d' % (n / dt, n, hits))
except Exception as e:
    print('YOLO_TEST_ERR', repr(e))
finally:
    try:
        if sensor is not None:
            sensor.stop()
        Display.deinit()
        os.exitpoint(os.EXITPOINT_ENABLE_SLEEP)
        time.sleep_ms(200)
        MediaManager.deinit()
        print('CLEANUP DONE')
    except Exception as e:
        print('CLEANUP_ERR', repr(e))
