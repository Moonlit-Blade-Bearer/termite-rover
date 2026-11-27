#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多任务模型推理自检：给一段 CSV 窗口，输出 depth_mm / termite_prob / detected。"""
import csv
import sys

import numpy as np
import torch

ROOT = r'E:\白蚁\白蚁数据集'
CKPT = ROOT + r'\checkpoints\best_multitask.pth'
sys.path.insert(0, ROOT)
import config as C          # noqa: E402
import model                # noqa: E402
import pipeline             # noqa: E402


def load_window(csv_path, skip=0):
    rows = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        rd = csv.reader(f)
        next(rd)
        for i, row in enumerate(rd):
            if i < skip:
                continue
            if len(rows) >= C.WINDOW_LEN:
                break
            rows.append([float(x) for x in row[7:7 + C.N_RAW_COL]])
    return np.array(rows, dtype=np.float32)


def infer(net, stats, win):
    dyn, static_c = pipeline.svd_step(win)
    feats = pipeline.feature_step(dyn, static_c, norm=(stats[0], stats[1]))
    x = torch.from_numpy(feats).unsqueeze(0)
    with torch.no_grad():
        d, logit = net(x)
    depth = float(pipeline.decode_step(d.numpy().ravel(), stats[2], stats[3])[0])
    prob = float(torch.sigmoid(logit).item())
    return depth, prob


def main():
    ck = torch.load(CKPT, map_location='cpu')
    print('task', ck.get('task'), 'epoch', ck.get('epoch'))
    net = model.build_multitask_model()
    net.load_state_dict(ck['model_state'])
    net.eval()
    stats = (np.asarray(ck['feat_mean'], dtype=np.float32),
             np.asarray(ck['feat_std'], dtype=np.float32),
             float(ck['y_mean']), float(ck['y_std']))
    for path in sys.argv[1:]:
        win = load_window(path)
        depth, prob = infer(net, stats, win)
        print('%-90s depth=%.2fmm  P(termite)=%.3f  detected=%s'
              % (path.split('\\')[-1][:90], depth, prob, prob >= 0.5))


if __name__ == '__main__':
    main()
