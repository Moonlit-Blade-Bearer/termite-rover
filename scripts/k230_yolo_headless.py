# 在 K230 上无屏运行 YOLOv5 检测（结果打印到 REPL，不初始化 LCD）
from media.sensor import *
from media.media import *
from libs.YOLO import YOLOv5

import gc
import time

KMODEL = '/sdcard/examples/kmodel/fruit_det_yolov5n_320.kmodel'
LABELS = ['apple', 'banana', 'orange']
RGB = [640, 360]
N = 30

try:
    sensor = Sensor(fps=30)
    sensor.reset()
    sensor.set_framesize(w=RGB[0], h=RGB[1], chn=CAM_CHN_ID_2)
    sensor.set_pixformat(Sensor.RGBP888, chn=CAM_CHN_ID_2)
    MediaManager.init()
    sensor.run()
    print('SENSOR OK')

    yolo = YOLOv5(task_type='detect', mode='video', kmodel_path=KMODEL,
                  labels=LABELS, rgb888p_size=RGB, model_input_size=[320, 320],
                  display_size=RGB, conf_thresh=0.5, nms_thresh=0.45,
                  max_boxes_num=50, debug_mode=0)
    yolo.config_preprocess()
    print('YOLO OK')

    t0 = time.time()
    n = 0
    hits = 0
    while n < N:
        img = sensor.snapshot(chn=CAM_CHN_ID_2)
        res = yolo.run(img)
        n += 1
        if res:
            hits += 1
            print('DET', n, res)
        gc.collect()

    dt = time.time() - t0
    print('RESULT fps=%.1f frames=%d hits=%d' % (n / dt, n, hits))

    sensor.stop()
    yolo.deinit()
    MediaManager.deinit()
    print('CLEANUP DONE')
except Exception as e:
    print('YOLO_TEST_ERR', repr(e))
