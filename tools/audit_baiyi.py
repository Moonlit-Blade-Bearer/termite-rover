# -*- coding: utf-8 -*-
"""白蚁数据集一致性审计：扫描全部 session_metadata.json 与 capture_summary.json,
比对文件夹标签 / 文件名标签 / 元数据标签，输出覆盖矩阵与异常统计。"""
import json, os, re, sys, io, collections

sys.stdout = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit_out.txt"), "w", encoding="utf-8")
ROOT = r"E:\白蚁数据集"
GROUPS = ["有白蚁", "无白蚁"]

sessions = []
for g in GROUPS:
    for root, dirs, files in os.walk(os.path.join(ROOT, g)):
        if "session_metadata.json" in files:
            try:
                with open(os.path.join(root, "session_metadata.json"), encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception as e:
                meta = {"_load_err": str(e)}
            cs = {}
            cs_path = os.path.join(root, "capture_summary.json")
            if os.path.exists(cs_path):
                try:
                    with open(cs_path, encoding="utf-8") as f:
                        cs = json.load(f)
                except Exception as e:
                    cs = {"_load_err": str(e)}
            # 文件夹路径结构: 组/木种/地点N/湿润度/会话folder
            rel = os.path.relpath(root, ROOT).replace("\\", "/").split("/")
            folder = {
                "group": rel[0] if len(rel) > 0 else "",
                "wood": rel[1] if len(rel) > 1 else "",
                "location": rel[2] if len(rel) > 2 else "",
                "moisture": rel[3] if len(rel) > 3 else "",
                "session_folder": rel[4] if len(rel) > 4 else "",
            }
            # 从 meta["file_label"] 提取 thickness
            fl = meta.get("file_label", "")
            m = re.search(r"thickness-(\d+(?:\.\d+)?)mm", fl)
            fname_thickness = float(m.group(1)) if m else None
            mp = re.search(r"moisture-([\d.]+)pct", fl)
            fname_moisture = float(mp.group(1)) if mp else None
            ft = re.search(r"termite-([01])", fl)
            fname_termite = int(ft.group(1)) if ft else None
            t2000 = "T000000" not in fl and "20000101" in fl
            timestamp_bad = "20000101" in fl
            sessions.append(dict(root=root.replace(ROOT + os.sep, "").replace("\\", "/"), meta=meta, cs=cs, **folder,
                                 fname_thickness=fname_thickness, fname_moisture=fname_moisture,
                                 fname_termite=fname_termite, timestamp_bad=timestamp_bad,
                                 label=fl))

print("### 会话总数:", len(sessions))

# ---- 采集质量 ----
if sessions:
    fps = [s["cs"].get("mean_frame_rate_hz") for s in sessions if "mean_frame_rate_hz" in s["cs"]]
    inc = [s["cs"].get("incomplete_frames", 0) for s in sessions if s["cs"]]
    frc = [s["cs"].get("completed_frames", 0) for s in sessions if s["cs"]]
    dup = [s["cs"].get("duplicate_packets", 0) for s in sessions if s["cs"]]
    ooo = [s["cs"].get("out_of_order_packets", 0) for s in sessions if s["cs"]]
    drt = [s["cs"].get("requested_duration_sec", 0) for s in sessions if s["cs"]]
    elp = [s["cs"].get("elapsed_seconds", 0) for s in sessions if s["cs"]]
    print("### 采集质量（有 capture_summary 的会话）:")
    print("  会话数:", len(fps), "/ 全部:", len(sessions))
    if fps:
        fps_s = sorted(x for x in fps if x)
        print("  帧率 hz: min={:.2f} 中位={:.2f} max={:.2f}".format(fps_s[0], fps_s[len(fps_s)//2], fps_s[-1]))
        print("  完成帧数: min={} 中位={} max={}".format(min(frc), sorted(frc)[len(frc)//2], max(frc)))
        print("  incomplete 总和:", sum(inc), " out_of_order 总和:", sum(ooo), " duplicate 总和:", sum(dup))
        print("  时长: requested 均值={:.0f}s elapsed 均值={:.0f}s".format(sum(drt)/len(drt), sum(elp)/len(elp)))
        print("  未满 59,000 帧的会话数（<100s 不足）:", sum(1 for x in frc if x < 59000))

# ---- 标签一致性 ----
mismatch_thickness = [s for s in sessions if s["fname_thickness"] is not None
                      and s["meta"].get("board_thickness_mm") not in (None,)
                      and abs(s["fname_thickness"] - float(s["meta"].get("board_thickness_mm", -999))) > 0.01]
print("### 文件名厚度 vs metadata 厚度 不一致:", len(mismatch_thickness))
if mismatch_thickness[:5]:
    for s in mismatch_thickness[:5]:
        print("   ", s["root"], "fname=", s["fname_thickness"], "meta=", s["meta"].get("board_thickness_mm"))

bad_time = [s for s in sessions if s["timestamp_bad"]]
print("### 时间戳异常(20000101)的会话:", len(bad_time))

# ---- 覆盖矩阵：木种 × 厚度 × 有无白蚁 ----
wood_map = {"椴木": "basswood", "胡桃木": "walnut", "榉木": "beech", "樱桃木": "cherry"}
grid = collections.defaultdict(int)
for s in sessions:
    key = (s["group"], s["wood"], s["fname_thickness"], s["meta"].get("location"))
    grid[key] += 1
print("### 覆盖矩阵（组, 木种, thickness mm, 地点）-> 会话数:")
for k in sorted(grid, key=lambda x: (str(x[0]), str(x[1]), str(x[2]), str(x[3]))):
    print("   {} -> {}".format(k, grid[k]))

# 元数据的虚构字段检查
unk_fields = ["wood_type", "operator", "room", "board_id", "colony_id", "cavity_id"]
cnt = collections.Counter()
for s in sessions:
    for fld in unk_fields:
        v = str(s["meta"].get(fld, "?")).lower()
        if v in ("unknown", "none", ""):
            cnt[fld] += 1
print("### metadata 中字段为 unknown/none 的会话数（共 {} 会话）:".format(len(sessions)), dict(cnt))

# depth_mm 的取值分布
dd = collections.Counter()
for s in sessions:
    dd[s["meta"].get("depth_mm")] += 1
print("### depth_mm 取值分布（前 15）:", dict(list(dd.items())[:15]))

# 木种 / 有无白蚁 总会话数
pw = collections.Counter((s["group"], s["wood"]) for s in sessions)
print("### 组×木种 会话数:", dict(pw))
