#!/usr/bin/env python3
"""IWR6843AOPEVM 接收器：配置雷达 → 读 921600 数据口 → 解析 384 字节帧 → CSV + 原始流。

帧结构（与数据集 raw_uart 一致，实测 100 帧/秒）：
    384 字节 = magic(8) + 4 天线 × [ts(4) + 20 bin × (Q,I) int16]
    天线记录间隔 96 字节；wire 是 Q 在前、I 在后，CSV 按数据集惯例写成 I,Q。

CSV 列与数据集完全一致：
    frame_id, host_time_ns, host_time_iso_utc, device_ts_a1..a4,
    a1_b00_i, a1_b00_q, ..., a4_b19_q   （共 167 列）

用法：
    python3 radar_receiver.py --duration 30 --out-csv radar.csv --out-raw radar.bin
"""
import argparse
import datetime
import json
import os
import struct
import sys
import time

import serial

MAGIC = b'\x01\x01\x04\x03\x06\x05\x08\x07'
BLOCK = 384
N_ANT = 4
N_BIN = 20
REC = 96

HEADER = ['frame_id', 'host_time_ns', 'host_time_iso_utc',
          'device_ts_a1', 'device_ts_a2', 'device_ts_a3', 'device_ts_a4']
for a in range(1, N_ANT + 1):
    for b in range(N_BIN):
        HEADER.append('a%d_b%02d_i' % (a, b))
        HEADER.append('a%d_b%02d_q' % (a, b))


def configure(cfg_port, cfg_path):
    lines = [l.strip() for l in open(cfg_path)
             if l.strip() and not l.strip().startswith('%')]
    s = serial.Serial(cfg_port, 115200, timeout=1.0)
    time.sleep(0.3)
    s.write(b'\r')
    time.sleep(0.3)
    s.read(256)
    errors = []
    for line in lines:
        s.write((line + '\r').encode())
        time.sleep(0.08)
        resp = s.read(512).decode(errors='replace')
        if 'Error' in resp or 'error' in resp:
            errors.append((line, resp.strip()[-80:]))
        if line == 'configDataPort 921600 1':
            time.sleep(0.3)
    s.close()
    return errors


def parse_block(block):
    """返回 (ts[4], iq[4][20][2] 按 (I,Q))；结构不符返回 None。"""
    if len(block) != BLOCK or not block.startswith(MAGIC):
        return None
    ts = []
    iq = []
    for a in range(N_ANT):
        off = 8 + a * REC
        if off + 84 > len(block):
            return None
        ts.append(struct.unpack_from('<I', block, off)[0])
        vals = struct.unpack_from('<40h', block, off + 4)
        pairs = []
        for b in range(N_BIN):
            q = vals[2 * b]
            i = vals[2 * b + 1]
            pairs.append((i, q))
        iq.append(pairs)
    return ts, iq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cfg', default='/root/ros2_ws/radar_dataset.cfg')
    ap.add_argument('--cfg-port', default='/dev/radar_cfg')
    ap.add_argument('--data-port', default='/dev/radar_data')
    ap.add_argument('--duration', type=float, default=30.0)
    ap.add_argument('--out-csv', default='/root/ros2_ws/radar_capture.csv')
    ap.add_argument('--out-raw', default='')
    args = ap.parse_args()

    errors = configure(args.cfg_port, args.cfg)
    for line, err in errors:
        print('CFG_ERR %s -> %s' % (line, err))

    data = serial.Serial(args.data_port, 921600, timeout=0.2)
    time.sleep(0.2)
    data.reset_input_buffer()

    fcsv = open(args.out_csv, 'w', newline='')
    fcsv.write(','.join(HEADER) + '\n')
    fraw = open(args.out_raw, 'wb') if args.out_raw else None

    buf = bytearray()
    frames = 0
    bad = 0
    t0 = time.time()
    next_report = t0 + 5

    while time.time() - t0 < args.duration:
        buf += data.read(65536)
        while True:
            k = buf.find(MAGIC)
            if k < 0:
                # 保留尾部 7 字节，防止 magic 被截断
                if len(buf) > 7:
                    buf = buf[-7:]
                break
            if k > 0:
                buf = buf[k:]
            if len(buf) < BLOCK:
                break
            block = bytes(buf[:BLOCK])
            parsed = parse_block(block)
            if parsed is None:
                buf = buf[1:]
                bad += 1
                continue
            buf = buf[BLOCK:]

            ts, iq = parsed
            now = time.time()
            iso = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).isoformat()
            row = [str(frames), str(int(now * 1e9)), iso]
            row.extend(str(t) for t in ts)
            for a in range(N_ANT):
                for b in range(N_BIN):
                    i, q = iq[a][b]
                    row.append(str(i))
                    row.append(str(q))
            fcsv.write(','.join(row) + '\n')
            if fraw:
                fraw.write(block)
            frames += 1

        if time.time() >= next_report:
            el = time.time() - t0
            print('t=%.0fs frames=%d fps=%.1f bad=%d' % (el, frames, frames / el, bad))
            next_report += 5

    elapsed = time.time() - t0
    fcsv.close()
    if fraw:
        fraw.close()
    data.close()

    summary = {
        'frames': frames,
        'elapsed_seconds': elapsed,
        'mean_frame_rate_hz': frames / elapsed if elapsed else 0,
        'bad_blocks': bad,
        'csv': args.out_csv,
        'raw': args.out_raw or None,
        'config': args.cfg,
        'finished_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    with open(args.out_csv + '.summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
