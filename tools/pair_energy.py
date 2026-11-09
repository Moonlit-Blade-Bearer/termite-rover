# -*- coding: utf-8 -*-
"""配对信号判别检验：同(木种,地点,湿度,厚度)下 有白蚁 vs 无白蚁 的慢时间微动能量对比。

能量定义：逐通道去 DC 后的幅度 std（80 通道 = 4 天线 × 20 距离bin），
报告 全通道均值 / Top-5 通道均值 / 最大通道 —— Top-5 代表“局部白蚁团”的检测口径。
"""
import os, re, sys, json, collections

OUT = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pair_out.txt"), "w", encoding="utf-8")
sys.stdout = OUT

import numpy as np

try:
    import pandas as pd
    HAVE_PD = True
except Exception:
    HAVE_PD = False

ROOT = r"E:\白蚁数据集"
GROUPS = ["有白蚁", "无白蚁"]

# ---------- 建立 session 索引 ----------
sess = collections.defaultdict(dict)   # (wood, loc, moist, thickness) -> {group: [(dir, csvpath)]}
for g in GROUPS:
    for root, dirs, files in os.walk(os.path.join(ROOT, g)):
        if "session_metadata.json" in files:
            rel = os.path.relpath(root, ROOT).replace("\\", "/").split("/")
            if len(rel) < 5:
                continue
            gname, wood, loc, moist, folder = rel[0], rel[1], rel[2], rel[3], rel[4]
            m = re.search(r"thickness-(\d+(?:\.\d+)?)mm", " ".join(files))
            if not m:
                # 从 metadata 拿
                try:
                    with open(os.path.join(root, "session_metadata.json"), encoding="utf-8") as f:
                        meta = json.load(f)
                    thk = float(meta.get("board_thickness_mm", -1))
                except Exception:
                    thk = -1
            else:
                thk = float(m.group(1))
            csvs = [os.path.join(root, f) for f in files if f.endswith(".csv") and "iq" in f.lower()]
            if not csvs:
                continue
            csvs.sort(key=lambda p: os.path.getsize(p), reverse=True)
            key = (wood, loc, moist, thk)
            sess[key][gname] = (root, csvs[0])

# ---------- 能量计算 ----------
def motion_energy(csv_path, use_rows=4000):
    if HAVE_PD:
        head = pd.read_csv(csv_path, nrows=2)
        obj_cols = set(head.select_dtypes(include="object").columns)
        bad = re.compile(r"frame|time|moist|termit|thick|loc(ation)?|durati|magic|serial|^id$", re.I)
        data_cols = [c for c in head.columns if c not in obj_cols and not bad.search(str(c))]
        if len(data_cols) < 160:
            data_cols = [c for c in head.columns if c not in obj_cols][:160]
        df = pd.read_csv(csv_path, usecols=data_cols, dtype=np.float32, nrows=use_rows, low_memory=False)
        A = df.to_numpy(dtype=np.float32)
    else:
        A = np.loadtxt(csv_path, delimiter=",", skiprows=1, max_rows=use_rows).astype(np.float32)
    A = A[:use_rows]
    Z = A[:, 0::2] + 1j * A[:, 1::2]
    Z = Z - Z.mean(axis=0, keepdims=True)
    std_ch = np.sqrt((np.abs(Z) ** 2).mean(axis=0))
    return np.sqrt(std_ch ** 2), std_ch

def energy_summary(std_ch):
    top = np.sort(std_ch)[-5:].mean()
    return dict(mean=float(std_ch.mean()), top5=float(top), max=float(std_ch.max()))

# ---------- 选配对：低中高各 1 个 ----------
pairs = []
for key in sorted(sess):
    wood, loc, moist, thk = key
    d = sess[key]
    if "有白蚁" in d and "无白蚁" in d:
        pairs.append(key)

if pairs:
    def t(k):
        return k[3]
    picks = []
    alrady = set()
    for band, cond in (("低厚(<=15mm)", lambda t: t <= 15),
                       ("中厚(20-35mm)", lambda t: 20 <= t <= 35),
                       ("高厚(>=40mm)", lambda t: t >= 40)):
        cand = [k for k in pairs if cond(t(k)) and k not in alrady]
        cand.sort(key=lambda k: t(k))
        if cand:
            k = cand[len(cand) // 2]
            alrady.add(k)
            picks.append((band, k))
    for band, k in picks:
        d = sess[k]
        E = {}
        for g in ("有白蚁", "无白蚁"):
            root, csv = d[g]
            std_ch, full = motion_energy(csv, use_rows=4000)
            E[g] = energy_summary(std_ch)
            E[g]["_path"] = os.path.relpath(root, ROOT)
        r_mean = E["有白蚁"]["mean"] / max(E["无白蚁"]["mean"], 1e-9)
        r_top = E["有白蚁"]["top5"] / max(E["无白蚁"]["top5"], 1e-9)
        print(f"\n=== {band}  匹配格 {k} ===")
        for g in ("有白蚁", "无白蚁"):
            print(f"  {g}: mean={E[g]['mean']:.4f} top5={E[g]['top5']:.4f} max={E[g]['max']:.4f}  [{E[g]['_path']}]")
        print(f"  能量比(有/无): mean={r_mean:.2f}x ({20*np.log10(r_mean):+.1f} dB)   top5={r_top:.2f}x ({20*np.log10(r_top):+.1f} dB)")
else:
    print("未找到可配对的格子")

print("\nDONE")
OUT.close()
