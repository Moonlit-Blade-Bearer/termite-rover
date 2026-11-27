#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T9.4 多任务训练：板厚回归 + 白蚁二分类（共享骨干）。

用法:
    python train_termite_multitask.py --data-root "E:\\白蚁\\白蚁数据集" --epochs 60
    python train_termite_multitask.py --epochs 2      # 冒烟

协议（与 train_full.py 一致）:
    * 只用 split.json 的 session-held-out 划分
    * 归一化统计量只在 train 上拟合
    * 选点用 val AUC，测试集只在最后评估一次
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn

DEFAULT_ROOT = r'E:\白蚁\白蚁数据集'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-root', default=DEFAULT_ROOT)
    ap.add_argument('--batch', type=int, default=256)
    ap.add_argument('--epochs', type=int, default=60)
    ap.add_argument('--lr', type=float, default=1e-3)
    ap.add_argument('--wd', type=float, default=1e-4)
    ap.add_argument('--patience', type=int, default=15)
    ap.add_argument('--lambda-cls', type=float, default=1.0)
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--device', default=None)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    sys.path.insert(0, args.data_root)
    import config as C
    import dsutil as D
    import model as M
    import train_full as T

    device = args.device or ('cuda' if torch.cuda.is_available() else 'cpu')
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    gen = torch.Generator().manual_seed(args.seed)

    out_path = args.out or os.path.join(C.CKPT_DIR, 'best_multitask.pth')
    report_path = os.path.join(C.OUT_DIR, 'train_multitask_report.json')

    man = D.load_manifest()
    feats = np.load(D.ALL_FEATS, mmap_mode='r')
    tr = D.split_window_indices(man, 1)
    va = D.split_window_indices(man, 2)
    te = D.split_window_indices(man, 3)
    y_mm = man['y_mm']
    term = man['termite'].astype(np.float32)
    print('windows train/val/test = %d/%d/%d | device=%s'
          % (len(tr), len(va), len(te), device))
    print('termite rate train=%.3f val=%.3f test=%.3f'
          % (term[tr].mean(), term[va].mean(), term[te].mean()))

    # ---- 归一化：只用 train ----
    t0 = time.time()
    y_mean = float(y_mm[tr].mean())
    y_std = float(y_mm[tr].std())
    feat_mean, feat_std = T.fit_norm_stats(feats, tr)
    print('norm 统计: y_mean=%.3f y_std=%.3f (%.0fs)' % (y_mean, y_std, time.time() - t0))

    Xtr, yn_tr = T.load_normalized(feats, tr, feat_mean, feat_std, y_mm, y_mean, y_std)
    Xva, yn_va = T.load_normalized(feats, va, feat_mean, feat_std, y_mm, y_mean, y_std)
    c_tr = term[tr]
    c_va = term[va]
    yva_mm = y_mm[va].astype(np.float64)
    print('Xtr', Xtr.shape, 'Xva', Xva.shape)

    t_tr = torch.from_numpy(Xtr)
    t_yn = torch.from_numpy(yn_tr)
    t_ctr = torch.from_numpy(c_tr)
    t_va = torch.from_numpy(Xva).to(device)
    t_cva = torch.from_numpy(c_va).to(device)

    net = M.build_multitask_model().to(device)
    opt = torch.optim.Adam(net.parameters(), lr=args.lr, weight_decay=args.wd)
    mse = nn.MSELoss()
    bce = nn.BCEWithLogitsLoss()
    print('参数量:', M.count_params(net))

    from sklearn.metrics import roc_auc_score

    best = {'auc': -1.0, 'epoch': -1, 'state': None, 'val': None}
    history = []
    n = len(t_tr)
    for ep in range(1, args.epochs + 1):
        net.train()
        perm = torch.randperm(n, generator=gen)
        tot, nb = 0.0, 0
        t_ep = time.time()
        for a in range(0, n, args.batch):
            b = perm[a:a + args.batch]
            xb = t_tr[b].to(device, non_blocking=True)
            yb = t_yn[b].to(device, non_blocking=True)
            cb = t_ctr[b].to(device, non_blocking=True)
            opt.zero_grad(set_to_none=True)
            depth, logit = net(xb)
            loss = mse(depth.squeeze(-1), yb) + args.lambda_cls * bce(logit.squeeze(-1), cb)
            loss.backward()
            opt.step()
            tot += float(loss.detach())
            nb += 1

        net.eval()
        dpreds, logits = [], []
        with torch.no_grad():
            for a in range(0, len(t_va), 1024):
                d, l = net(t_va[a:a + 1024])
                dpreds.append(d.squeeze(-1).cpu().numpy())
                logits.append(l.squeeze(-1).cpu().numpy())
        dnorm = np.concatenate(dpreds).astype(np.float64)
        prob = 1.0 / (1.0 + np.exp(-np.concatenate(logits).astype(np.float64)))
        vm, _ = T.metrics_mm(dnorm, yva_mm, y_mean, y_std)
        auc = float(roc_auc_score(c_va, prob))
        acc = float(((prob >= 0.5) == (c_va > 0.5)).mean())
        history.append({'epoch': ep, 'loss': round(tot / max(nb, 1), 5),
                        'val_auc': round(auc, 4), 'val_acc': round(acc, 4),
                        'val_mae_mm': vm['MAE'], 'sec': round(time.time() - t_ep, 1)})
        improved = auc > best['auc'] + 1e-6
        if improved:
            best = {'auc': auc, 'epoch': ep, 'val': {'auc': auc, 'acc': acc, 'mae': vm['MAE']},
                    'state': {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}}
        print('epoch %3d/%d loss=%.4f val AUC=%.4f acc=%.4f MAE=%.3fmm %s (%.1fs)'
              % (ep, args.epochs, tot / max(nb, 1), auc, acc, vm['MAE'],
                 '*best*' if improved else '', time.time() - t_ep), flush=True)
        if ep - best['epoch'] >= args.patience:
            print('早停：连续 %d 轮 val AUC 未改善（best epoch %d, AUC %.4f）'
                  % (args.patience, best['epoch'], best['auc']))
            break

    # ---- 测试集（只评一次）----
    net.load_state_dict(best['state'])
    net.eval()
    Xte, yn_te = T.load_normalized(feats, te, feat_mean, feat_std, y_mm, y_mean, y_std)
    t_te = torch.from_numpy(Xte).to(device)
    dpreds, logits = [], []
    with torch.no_grad():
        for a in range(0, len(t_te), 1024):
            d, l = net(t_te[a:a + 1024])
            dpreds.append(d.squeeze(-1).cpu().numpy())
            logits.append(l.squeeze(-1).cpu().numpy())
    prob = 1.0 / (1.0 + np.exp(-np.concatenate(logits).astype(np.float64)))
    c_te = term[te]
    test_auc = float(roc_auc_score(c_te, prob))
    pred = (prob >= 0.5).astype(np.int8)
    tp = int(((pred == 1) & (c_te == 1)).sum())
    tn = int(((pred == 0) & (c_te == 0)).sum())
    fp = int(((pred == 1) & (c_te == 0)).sum())
    fn = int(((pred == 0) & (c_te == 1)).sum())
    test_metrics = {
        'auc': round(test_auc, 4),
        'accuracy': round(float((pred == c_te).mean()), 4),
        'sensitivity': round(tp / max(tp + fn, 1), 4),
        'specificity': round(tn / max(tn + fp, 1), 4),
        'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn,
    }
    dm, _ = T.metrics_mm(np.concatenate(dpreds).astype(np.float64),
                         y_mm[te].astype(np.float64), y_mean, y_std)
    test_metrics['depth'] = dm

    ck = {
        'model_state': best['state'],
        'task': 'multitask',
        'feat_mean': torch.from_numpy(feat_mean),
        'feat_std': torch.from_numpy(feat_std),
        'y_mean': y_mean,
        'y_std': y_std,
        'cfg': {'window_len': C.WINDOW_LEN, 'n_raw_col': C.N_RAW_COL, 'svd_k': C.SVD_K,
                'n_bands': C.N_BANDS, 'f_channels': C.F_CHANNELS, 'n_ch': C.N_CH,
                'conv_channels': C.CONV_CHANNELS, 'fc_dim': C.FC_DIM,
                'dropout': C.DROPOUT, 'thickness_max': C.THICKNESS_MAX},
        'epoch': best['epoch'],
        'val_metrics': best['val'],
        'test_metrics': test_metrics,
    }
    tmp = out_path + '.tmp'
    torch.save(ck, tmp)
    os.replace(tmp, out_path)
    report = {'args': vars(args), 'best_epoch': best['epoch'], 'best_val': best['val'],
              'test': test_metrics, 'history': history}
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    print('\n==== 测试集 ====')
    print(json.dumps(test_metrics, ensure_ascii=False, indent=1))
    print('checkpoint ->', out_path)
    print('report ->', report_path)


if __name__ == '__main__':
    main()
