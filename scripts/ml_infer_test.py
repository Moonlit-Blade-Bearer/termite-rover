#!/usr/bin/env python3
"""在 Jetson 上用采集到的雷达 CSV 跑一次 CNN 推理，验证模型与耗时。"""
import csv
import sys
import time

import numpy as np
import torch

sys.path.insert(0, '/home/chl/termite-rover/ml')
import config as C          # noqa: E402
import model                # noqa: E402
import pipeline             # noqa: E402

CKPT = '/home/chl/termite-rover/ml/best_full.pth'
CSV = sys.argv[1] if len(sys.argv) > 1 else '/home/chl/ros2_ws/radar_test.csv'
SKIP = int(sys.argv[2]) if len(sys.argv) > 2 else 0

print('numpy', np.__version__, 'torch', torch.__version__)
ck = torch.load(CKPT, map_location='cpu')
print('ckpt keys', list(ck.keys()))

net = model.build_model()
net.load_state_dict(ck['model_state'])
net.eval()
stats = (np.asarray(ck['feat_mean'], dtype=np.float32),
         np.asarray(ck['feat_std'], dtype=np.float32),
         float(ck['y_mean']), float(ck['y_std']))
print('norm stats ok, params', model.count_params(net))

rows = []
with open(CSV) as f:
    rd = csv.reader(f)
    next(rd)
    for i, row in enumerate(rd):
        if i < SKIP:
            continue
        if len(rows) >= C.WINDOW_LEN:
            break
        rows.append([float(x) for x in row[7:7 + C.N_RAW_COL]])
raw = np.array(rows, dtype=np.float32)
print('window', raw.shape)

t0 = time.time()
depth, times = pipeline.full_pipeline(raw, net, stats, device='cpu')
dt = time.time() - t0
print('depth_mm=%.2f' % depth)
print('stages_ms', {k: round(v * 1000, 1) for k, v in times.items()})
print('wall_ms=%.1f' % (dt * 1000))

deps = []
t0 = time.time()
for i in range(10):
    d, _ = pipeline.full_pipeline(raw, net, stats, device='cpu')
    deps.append(d)
dt = time.time() - t0
print('avg_ms=%.1f  depth_min/max=%.2f/%.2f' % (dt * 100, min(deps), max(deps)))
