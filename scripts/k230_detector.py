# K230 检测器：YOLOv8n 320，无屏运行，通过 USB CDC 发送带 CRC 的检测帧
# 帧格式（ASCII 行，便于调试）：
#   $D,<seq>,<json>,<crc16>\n
#   json = {"w":640,"h":360,"fps":19.1,"d":[["person",x,y,w,h,score],...]}
#   crc16 = CRC-16/CCITT-FALSE(json)，4 位十六进制
from media.sensor import *
from media.display import *
from media.media import *
from libs.YOLO import YOLOv8

import gc
import os
import time
import ujson

KMODEL = '/sdcard/examples/kmodel/yolov8n_320.kmodel'
W, H = 640, 360
SEND_EVERY = 2          # 每 2 帧发一次（约 9~10 Hz）

_txt = open('/sdcard/examples/05-AI-Demo/object_detect_yolov8n.py').read()
LABELS = ['person']
for _l in _txt.split('\n'):
    if _l.strip().startswith('labels'):
        try:
            LABELS = eval(_l.split('=', 1)[1].strip())
        except Exception:
            pass
        break


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


sensor = None
yolo = None
seq = 0
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
    print('$READY K230 detector')   # 主机看到这行就认为已就绪

    t0 = time.ticks_ms()
    n = 0
    while True:
        img = sensor.snapshot(chn=CAM_CHN_ID_2)
        res = yolo.run(img.to_numpy_ref())
        n += 1

        if n % SEND_EVERY == 0:
            boxes, ids, scores = res[0], res[1], res[2]
            dets = []
            for i in range(len(boxes)):
                x, y, w, h = [int(v) for v in boxes[i]]
                cls = int(ids[i])
                name = LABELS[cls] if cls < len(LABELS) else str(cls)
                dets.append([name, x, y, w, h, round(float(scores[i]), 3)])

            dt = time.ticks_diff(time.ticks_ms(), t0)
            fps = round(n * 1000.0 / max(dt, 1), 1)
            payload = ujson.dumps({'w': W, 'h': H, 'fps': fps, 'd': dets})
            crc = crc16(payload.encode())
            seq += 1
            print('$D,%d,%s,%04X' % (seq, payload, crc))
        gc.collect()
except Exception as e:
    print('$ERR', repr(e))
finally:
    try:
        if sensor is not None:
            sensor.stop()
        Display.deinit()
        os.exitpoint(os.EXITPOINT_ENABLE_SLEEP)
        time.sleep_ms(200)
        MediaManager.deinit()
        print('$STOP')
    except Exception as e:
        print('$CLEANUP_ERR', repr(e))
