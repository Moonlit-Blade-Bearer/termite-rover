# -*- coding: utf-8 -*-
"""健壮版配对检验：每个厚度档找多对 (木种,地点,湿度)完全一致的 有/无白蚁 会话，
每个会话取 2 个跨时长窗口（开头 + 中后段）计算 80 通道去DC 后的 RMS 能量，
用 top5 通道能量比判断信号对比度。纯 csv + numpy，避免 pandas skiprows 语义问题。"""
import os, re, sys, json, csv, itertools
import numpy as np

OUT = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pair2_out.txt"), "w", encoding="utf-8")
sys.stdout = OUT

ROOT = r"E:\白蚁数据集"
GROUPS = ["有白蚁", "无白蚁"]
CHUNK_ROWS = 3000
OFFSETS = [1, 24001]          # 跳过的数据行数（即取第 0 个与第 24000 个样本窗口）

# ---------- 会话注册 ----------
def norm_key(wood, loc, moist, thk):
    return (wood, str(loc), moist, thk)

reg = {}
for g in GROUPS:
    reg[g] = {}
    for root, dirs, files in os.walk(os.path.join(ROOT, g)):
        if "session_metadata.json" not in files:
            continue
        rel = os.path.relpath(root, ROOT).replace("\\", "/").split("/")
        if len(rel) < 5:
            continue
        wood, loc, moist, folder = rel[1], rel[2], rel[3], rel[4]
        try:
            with open(os.path.join(root, "session_metadata.json"), encoding="utf-8") as f:
                meta = json.load(f)
            thk = float(meta.get("board_thickness_mm", -1))
        except Exception:
            thk = -1
        csvs = sorted([os.path.join(root, f) for f in files
                       if f.lower().endswith(".csv") and "iq" in f.lower()],
                      key=lambda p: os.path.getsize(p), reverse=True)
        if not csvs or thk < 0:
            continue
        k = norm_key(wood, loc, moist, thk)
        reg[g].setdefault(k, []).append(os.path.join(root, csvs[0]))

# ---------- 数据列定位（解析一次表头） ----------
BAD_COLS = re.compile(r"frame|time|moist|termit|thick|loc(ation)?|durati|magic|serial|^id$|^prev|ascii", re.I)

def find_data_cols(path):
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        header = next(csv.reader(f))
    idx = [i for i, c in enumerate(header) if not BAD_COLS.search(str(c))]
    if len(idx) != 160:
        idx = list(range(len(header) - 160, len(header)))   # 兜底：最后 160 列
    return idx

def chunk_rms_top5(path, data_cols, offset):
    """读 offset 起 CHUNK_ROWS 行，返回去DC后 80 通道 RMS 的 top5 均值与全均值。"""
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            r = csv.reader(f)
            next(r)                                   # 表头
            for _ in range(offset - 1):
                next(r)
            L = []
            for i, row in zip(range(CHUNK_ROWS), itertools.islice(r, CHUNK_ROWS)):
                if len(row) <= data_cols[-1]:
                    continue
                try:
                    vals = [float(row[j]) for j in data_cols]
                except ValueError:
                    continue
                L.append(vals)
        if len(L) < 1500:
            return None
        A = np.asarray(L, dtype=np.float32)
        Z = A[:, 0::2] + 1j * A[:, 1::2]
        Z -= Z.mean(axis=0, keepdims=True)
        rms = np.sqrt((np.abs(Z) ** 2).mean(axis=0))
        return float(np.sort(rms)[-5:].mean()), float(rms.mean())
    except Exception as e:
        print("  [ERR]", os.path.basename(path), repr(e)[:80])
        return None

def session_energy(path, data_cols):
    vals = []
    for off in OFFSETS:
        c = chunk_rms_top5(path, data_cols, off)
        if c:
            vals.append(c)
        else:
            c2 = chunk_rms_top5(path, data_cols, 12001)   # 兜底中段
            if c2:
                vals.append(c2)
    if not vals:
        return None
    top5 = float(np.mean([v[0] for v in vals]))
    mean = float(np.mean([v[1] for v in vals]))
    n = len(vals)
    frac_pos = float(np.mean([1.0 if vals[i][0] > 0 else 0 for i in range(n)]))
    return top5, mean, n

# ---------- 主循环 ----------
thicknesses = [5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0]
results = {}
for thk in thicknesses:
    common = sorted(set(reg["有白蚁"]) & set(reg["无白蚁"]) & {k for k in reg["无白蚁"] if k[3] == thk})
    if not common:
        print(f"\n厚度 {thk:5.1f} mm: 无匹配配对")
        continue
    common = common[:2]      # 每厚度最多 2 对，控时
    rows = []
    for k in common:
        p_t = reg["有白蚁"][k][0]
        p_n = reg["无白蚁"][k][0]
        dt = find_data_cols(p_t); dn = find_data_cols(p_n)
        et = session_energy(p_t, dt)
        en = session_energy(p_n, dn)
        if et and en:
            ratio = et[0] / max(en[0], 1e-9)
            rows.append((k, et, en, 20 * np.log10(max(ratio, 1e-9))))
    if not rows:
        print(f"\n厚度 {thk:5.1f} mm: 配对会话读取失败")
        continue
    cs = [r[3] for r in rows]
    win = sum(1 for c in cs if c > 1.0)
    results[thk] = cs
    print(f"\n=== 厚度 {thk:5.1f} mm  配对数 {len(rows)} ===")
    for k, et, en, cdb in rows:
        print(f"  格 {k}")
        print(f"    有白蚁 top5={et[0]:9.1f} mean={et[1]:8.1f} (n窗口={et[2]})")
        print(f"    无白蚁 top5={en[0]:9.1f} mean={en[1]:8.1f} (n窗口={en[2]})")
        print(f"    对比度 = {cdb:+.1f} dB")
    print(f"  >>> 中位 {np.median(cs):+.1f} dB  范围 [{min(cs):+.1f}, {max(cs):+.1f}]  正向对数 {win}/{len(cs)}")

print("\n=== 汇总表 (对比度 dB: 有白蚁能量/无白蚁能量) ===")
for thk, cs in results.items():
    print(f"  {thk:5.1f} mm: 中位 {np.median(cs):+6.1f}  (n={len(cs)})")

print("\nDONE")
OUT.close()
