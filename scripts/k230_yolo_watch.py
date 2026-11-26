# K230 连续检测 20 秒：站在镜头前应能持续检出 person
from media.sensor import *
from media.display import *
from media.media import *
from libs.YOLO import YOLOv8

import gc
import os
import time

KMODEL = '/sdcard/examples/kmodel/yolov8n_320.kmodel'
W, H = 640, 360
N = 400          # 约 20 秒 @19FPS

LABELS = ['person']
_txt = open('/sdcard/examples/05-AI-Demo/object_detect_yolov8n.py').read()
for _l in _txt.split('\n'):
    if _l.strip().startswith('labels'):
        try:
            LABELS = eval(_l.split('=', 1)[1].strip())
        except Exception:
            pass
        break

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

    for _ in range(5):
        sensor.snapshot(chn=CAM_CHN_ID_2)

    yolo = YOLOv8(task_type='detect', mode='video', kmodel_path=KMODEL,
                  labels=LABELS, rgb888p_size=[W, H], model_input_size=[320, 320],
                  display_size=[W, H], conf_thresh=0.4, nms_thresh=0.45,
                  max_boxes_num=50, debug_mode=0)
    yolo.config_preprocess()
    print('WATCHING')

    t0 = time.ticks_ms()
    n = 0
    with_det = 0
    best = 0.0
    while n < N:
        img = sensor.snapshot(chn=CAM_CHN_ID_2)
        res = yolo.run(img.to_numpy_ref())
        n += 1
        for ci, boxes in enumerate(res):
            if boxes and LABELS[ci] == 'person':
                with_det += 1
                for b in boxes:
                    conf = b[-1] if isinstance(b[-1], (int, float)) else 0
                    if conf > best:
                        best = conf
                if with_det % 10 == 1:
                    print('F%d PERSON %s' % (n, boxes[:1]))
                break
        gc.collect()

    dt = time.ticks_diff(time.ticks_ms(), t0)
    print('SUMMARY frames=%d person_frames=%d best_conf=%.2f ms=%d fps=%.1f' % (
        n, with_det, best, dt, n * 1000.0 / max(dt, 1)))
except Exception as e:
    print('WATCH_ERR', repr(e))
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
