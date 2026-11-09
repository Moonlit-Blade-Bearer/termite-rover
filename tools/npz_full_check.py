# -*- coding: utf-8 -*-
"""npz + checkpoint 全量验证：读取 val_metrics，加载 model_state，跑完 1100 个测试窗口，算指标。"""
import os, sys, json

OUT = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "npz_full_out.txt"), "w", encoding="utf-8")
sys.stdout = OUT

import numpy as np

npz_path = r"E:\白蚁数据集\模型\test_windows_full.npz"
ckpt_path = r"E:\白蚁数据集\模型\best_full.pth"
code_dir = r"E:\白蚁数据集\代码"

d = np.load(npz_path, allow_pickle=True)
X, Y = d["x"], d["y"].astype(np.float64)
print("=== npz ===")
print("x:", X.shape, X.dtype, " y unique:", np.unique(Y))

import torch
ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
print("\n=== checkpoint 元数据 ===")
print("epoch:", ck.get("epoch"))
print("cfg:", ck.get("cfg"))
print("data:", ck.get("data"))
print("val_metrics:", ck.get("val_metrics"))
print("y_mean:", float(ck["y_mean"]), " y_std:", float(ck["y_std"]))
fm, fs = ck["feat_mean"], ck["feat_std"]
print("feat_mean shape:", np.asarray(fm).shape, "feat_std shape:", np.asarray(fs).shape)

sys.path.insert(0, code_dir)
import pipeline as P
import model as M
import config as C

net = M.DepthCNN()
net.load_state_dict(ck["model_state"])
net.eval()
print("\n模型加载成功;开始 1100 窗口推理…")

norm = (np.asarray(fm, dtype=np.float64), np.asarray(fs, dtype=np.float64),
        float(ck["y_mean"]), float(ck["y_std"]))

preds = np.empty(len(X), dtype=np.float64)
for i in range(len(X)):
    mm, times = P.full_pipeline(X[i], net, norm, device="cpu")
    preds[i] = mm
    if i % 200 == 0:
        OUT.flush()
        print(f"  {i}/{len(X)}  已耗时…")

err = preds - Y
mae = np.abs(err).mean()
rmse = float(np.sqrt((err ** 2).mean()))
ss_res = float((err ** 2).sum())
ss_tot = float(((Y - Y.mean()) ** 2).sum())
r2 = 1 - ss_res / ss_tot
print("\n=== 总体指标（1100 测试窗口，7K=SVD去静杂波完整管线） ===")
print(f"MAE = {mae:.3f} mm   RMSE = {rmse:.3f} mm   R2 = {r2:.4f}")

print("\n=== 按标签厚度分组的预测统计 ===")
for t in np.unique(Y):
    m = Y == t
    print(f"  厚度 {t:5.1f} mm: n={m.sum():4d}  预测均值={preds[m].mean():7.2f}  偏差均值={err[m].mean():+7.2f}  MAE={np.abs(err[m]).mean():6.2f}  预测std={preds[m].std():6.2f}")

# 以最近档位评估分类（每 5mm 一档）
round5 = np.round(Y / 5.0) * 5.0
acc5 = (np.abs(preds - Y) <= 2.5).mean()
within5 = (np.abs(preds - round5) <= 2.5).mean()
print(f"\n|err|<=2.5mm(半档) 比例: {acc5:.3f}   预测∈本档±2.5mm 比例(四舍五入到档): {within5:.3f}")

np.savez(os.path.join(os.path.dirname(os.path.abspath(__file__)), "preds_test.npz"),
         y=Y, preds=preds)
print("\nDONE")
OUT.close()
