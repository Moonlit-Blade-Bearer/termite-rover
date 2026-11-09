# -*- coding: utf-8 -*-
"""检查 test_windows_full.npz 与 best_full.pth：键、形状、标签分布，并用 pipeline 实际推理 3 个窗口。"""
import os, sys, json

OUT = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "npz_out.txt"), "w", encoding="utf-8")
sys.stdout = OUT

import numpy as np

npz_path = r"E:\白蚁数据集\模型\test_windows_full.npz"
ckpt_path = r"E:\白蚁数据集\模型\best_full.pth"
code_dir = r"E:\白蚁数据集\代码"

d = np.load(npz_path, allow_pickle=True)
print("=== npz keys ===")
for k in d.keys():
    arr = d[k]
    if hasattr(arr, "shape"):
        print(f"  {k}: shape={arr.shape} dtype={arr.dtype}")
        if arr.dtype.kind in "fiu" and arr.size and arr.size < 200000:
            flat = np.asarray(arr, dtype=np.float64).ravel()
            if flat.size:
                print(f"      min={flat.min():.4f} max={flat.max():.4f} mean={flat.mean():.4f}")
                uniq = np.unique(flat)
                if uniq.size <= 40:
                    print(f"      unique(<=40): {uniq}")
        elif arr.dtype == object or arr.dtype.kind in "US":
            vals = arr.ravel()
            uniq = list(dict.fromkeys([str(v)[:120] for v in vals[:60]]))
            print(f"      前 60 个值(去重): {uniq}")
    else:
        print(f"  {k}: {type(arr)} -> {arr}")

# torch 与权重
try:
    import torch
    print("\n=== torch", torch.__version__, "cuda:", torch.cuda.is_available(), "===")
    ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    if isinstance(ck, dict):
        print("checkpoint 顶层键:", list(ck.keys())[:20])
        sd_key = None
        for cand in ("model_state_dict", "state_dict", "model", "best"):
            if cand in ck and hasattr(ck[cand], "keys"):
                sd_key = cand
        if sd_key:
            sd = ck[sd_key]
            for k2 in ("norm_mean", "norm_std", "feat_mean", "feat_std", "y_mean", "y_std"):
                if k2 in ck and hasattr(ck[k2], "shape"):
                    print(f"  伴随数组 {k2}: shape={ck[k2].shape} 值域={ck[k2].min():.4f}~{ck[k2].max():.4f}")
        else:
            sd = ck if hasattr(ck, "keys") else None
        if sd is None:
            for v in ck.values():
                if hasattr(v, "keys"):
                    sd = v
                    break
        if sd is not None:
            print("  权重张量形状:")
            for k2, v in list(sd.items())[:25]:
                print(f"    {k2}: {tuple(v.shape)}")
except Exception as e:
    print("torch 部分异常:", repr(e))

# 实际推理
try:
    sys.path.insert(0, code_dir)
    import pipeline as P
    import model as M
    import config as C
    print("\n=== config 备忘 ===")
    print("WINDOW_LEN:", C.WINDOW_LEN, " N_ANT:", C.N_ANT, " N_BIN:", C.N_BIN,
          " SVD_K:", C.SVD_K, " N_BANDS:", C.N_BANDS, " F_CHANNELS:", C.F_CHANNELS,
          " THICKNESS_MAX:", C.THICKNESS_MAX, " WINDOWS_PER_SESSION:", C.WINDOWS_PER_SESSION)
    net = M.DepthCNN()
    loaded = False
    if isinstance(ck, dict):
        for cand in ("model_state_dict", "state_dict", "model", "best"):
            if cand in ck:
                try:
                    net.load_state_dict(ck[cand])
                    loaded = True
                    break
                except Exception as e2:
                    print(f"  load {cand} 失败: {e2}")
        if not loaded:
            try:
                net.load_state_dict(ck)
                loaded = True
            except Exception as e3:
                print("  直接加载失败:", e3)
    print("  模型加载成功:", loaded)

    if loaded and "x" in d:
        X = d["x"]
        print("  X shape:", X.shape)
        ys = None
        for cand in ("y", "y_norm", "depth", "depth_mm", "labels"):
            if cand in d:
                ys = d[cand]
                break
        for idx in range(min(3, X.shape[0])):
            win = X[idx] if X.ndim == 3 else X[idx, 0] if X.ndim == 4 else X
            depth, times = P.full_pipeline(win, net, (np.zeros(1), np.ones(1), 0.0, 1.0))
            # norm 用 0/1 占位(如果 npz / ckpt 里有真实 norm 会更准，但形状未知时先占位)
            print(f"  窗口[{idx}] 推理输出(占位norm): depth_mm={depth:.3f}  T_total={times['T_total']*1000:.1f}ms")
            if ys is not None and ys.size > idx:
                try:
                    print(f"      标记录值: {ys[idx]}")
                except Exception:
                    pass
except Exception as e:
    import traceback
    print("pipeline 实际推理异常:", repr(e))
    traceback.print_exc(file=OUT)

print("\nDONE")
OUT.close()
