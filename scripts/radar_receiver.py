#!/usr/bin/env python3
"""IWR6843AOPEVM 接收器：配置雷达 → 读 921600 → 解析 → CSV/原始流。

解析使用厂商原始采集工具的算法（`termite_bringup.radar_iq`）：
    - 每个天线一个 magic（0x0708050603040101..0104）
    - 包 = magic(8) + ts(4) + 20 bin × (Q,I) int16 = 92 字节
    - 包间分隔符 "f\\r\\n"（另有 1 字节被丢弃）
    - 4 个天线包组成一帧（天线 0 标记帧首）
    - wire 是 Q,I；CSV 按数据集惯例写 I,Q

用法：
    python3 radar_receiver.py --duration 30 --out-csv radar.csv --out-raw radar.bin
"""
import argparse
import csv
import datetime
import json
import time

import serial

from termite_bringup.radar_iq import FrameAssembler, PacketStreamParser

CFG_HEADER = ['frame_id', 'host_time_ns', 'host_time_iso_utc',
              'device_ts_a1', 'device_ts_a2', 'device_ts_a3', 'device_ts_a4']
for _a in range(1, 5):
    for _b in range(20):
        CFG_HEADER.append('a%d_b%02d_i' % (_a, _b))
        CFG_HEADER.append('a%d_b%02d_q' % (_a, _b))


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
        if 'error' in resp.lower():
            errors.append((line, resp.strip()[-80:]))
        if line == 'configDataPort 921600 1':
            time.sleep(0.3)
    s.close()
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cfg', default='/root/ros2_ws/radar_dataset.cfg')
    ap.add_argument('--cfg-port', default='/dev/radar_cfg')
    ap.add_argument('--data-port', default='/dev/radar_data')
    ap.add_argument('--duration', type=float, default=30.0)
    ap.add_argument('--out-csv', default='/root/ros2_ws/radar_capture.csv')
    ap.add_argument('--out-raw', default='')
    args = ap.parse_args()

    for line, err in configure(args.cfg_port, args.cfg):
        print('CFG_ERR %s -> %s' % (line, err))

    data = serial.Serial(args.data_port, 921600, timeout=0.2)
    time.sleep(0.2)
    data.reset_input_buffer()

    fraw = open(args.out_raw, 'wb') if args.out_raw else None
    parser = PacketStreamParser(range_bins=20, raw_sink=fraw)
    assembler = FrameAssembler(antenna_count=4, range_bins=20)

    fcsv = open(args.out_csv, 'w', newline='')
    writer = csv.writer(fcsv, lineterminator='\n')
    writer.writerow(CFG_HEADER)

    frames = 0
    t0 = time.time()
    next_report = t0 + 5

    while time.time() - t0 < args.duration:
        chunk = data.read(65536)
        if not chunk:
            continue
        for pkt in parser.feed(chunk):
            frame = assembler.add(pkt)
            if frame is None:
                continue
            iso = datetime.datetime.fromtimestamp(
                frame.host_time_ns / 1e9, datetime.timezone.utc
            ).isoformat(timespec='microseconds')
            row = [frame.frame_id, frame.host_time_ns, iso]
            row.extend(frame.device_timestamps)
            row.extend(frame.iq.reshape(-1).astype(int).tolist())
            writer.writerow(row)
            frames += 1
        if frames and frames % 500 == 0:
            fcsv.flush()
        if time.time() >= next_report:
            el = time.time() - t0
            print('t=%.0fs frames=%d fps=%.1f pkts=%d bad=%d' % (
                el, frames, frames / el, parser.parsed_packets, assembler.out_of_order_packets))
            next_report += 5

    parser.finish()
    assembler.finish()
    fcsv.close()
    if fraw:
        fraw.close()
    data.close()
    elapsed = time.time() - t0

    summary = {
        'frames': frames,
        'elapsed_seconds': elapsed,
        'mean_frame_rate_hz': frames / elapsed if elapsed else 0,
        'packets': parser.parsed_packets,
        'transport_separator_bytes': parser.transport_separator_bytes,
        'discarded_stream_bytes': parser.discarded_bytes,
        'incomplete_frames': assembler.incomplete_frames,
        'out_of_order_packets': assembler.out_of_order_packets,
        'duplicate_packets': assembler.duplicate_packets,
        'csv': args.out_csv,
        'raw': args.out_raw or None,
        'finished_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    with open(args.out_csv + '.summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
