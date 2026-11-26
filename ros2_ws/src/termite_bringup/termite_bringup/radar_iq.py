"""TI mmWave 1D-FFT complex I/Q acquisition utilities.

This module records the earliest complex data exposed by the current UART
protocol: complex 1D range-FFT bins. These are NOT raw ADC samples.
"""

import csv
import json
import os
import struct
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Dict, List, Optional, TextIO, Tuple

import numpy as np


# Existing firmware protocol used in the student's project.
_MAGIC_VALUES = (
    0x0708050603040101,
    0x0708050603040102,
    0x0708050603040103,
    0x0708050603040104,
)
MAGIC_TO_ANTENNA: Dict[bytes, int] = {
    struct.pack("<Q", value): antenna_id
    for antenna_id, value in enumerate(_MAGIC_VALUES)
}
MAGIC_WORDS: Tuple[bytes, ...] = tuple(MAGIC_TO_ANTENNA)
TRANSPORT_SEPARATOR = b"f\r\n"


class CaptureMetadata(object):
    def __init__(self, session_id, file_label="", data_kind="range_fft_complex_iq",
                 activity=-1, termite_present=-1, depth_mm=-1.0,
                 depth_definition="cavity_center_normal_depth_from_wood_front_surface",
                 board_thickness_mm=-1.0, location=-1, wood_type="unknown",
                 moisture_percent=-1.0, board_id="unknown", colony_id="unknown",
                 cavity_id="unknown", operator="unknown", room="unknown", notes="",
                 range_bins=20, antenna_count=4, serial_baudrate=921600,
                 radar_config_file="", created_utc="", collection_time_local="",
                 requested_duration_sec=0.0):
        self.session_id = session_id
        self.file_label = file_label
        self.data_kind = data_kind
        self.activity = activity
        self.termite_present = termite_present
        self.depth_mm = depth_mm
        self.depth_definition = depth_definition
        self.board_thickness_mm = board_thickness_mm
        self.location = location
        self.wood_type = wood_type
        self.moisture_percent = moisture_percent
        self.board_id = board_id
        self.colony_id = colony_id
        self.cavity_id = cavity_id
        self.operator = operator
        self.room = room
        self.notes = notes
        self.range_bins = range_bins
        self.antenna_count = antenna_count
        self.serial_baudrate = serial_baudrate
        self.radar_config_file = radar_config_file
        self.created_utc = created_utc
        self.collection_time_local = collection_time_local
        self.requested_duration_sec = requested_duration_sec


class ParsedPacket(object):
    def __init__(self, antenna_id, device_timestamp, iq, host_time_ns):
        self.antenna_id = antenna_id
        self.device_timestamp = device_timestamp
        self.iq = iq
        self.host_time_ns = host_time_ns


class CompletedFrame(object):
    def __init__(self, frame_id, host_time_ns, device_timestamps, iq):
        self.frame_id = frame_id
        self.host_time_ns = host_time_ns
        self.device_timestamps = device_timestamps
        self.iq = iq


class PacketStreamParser:
    """Incrementally extracts fixed-length packets from an arbitrary byte stream.

    The old code used ``readline()`` on binary radar data. That can split a packet
    whenever an I/Q byte happens to equal a newline byte. This parser instead scans
    for the 8-byte magic word and consumes a fixed-size packet.
    """

    def __init__(self, range_bins: int = 20, raw_sink: Optional[BinaryIO] = None):
        if range_bins <= 0:
            raise ValueError("range_bins must be positive")
        self.range_bins = range_bins
        self.packet_size = 8 + 4 + range_bins * 4
        self.buffer = bytearray()
        self.raw_sink = raw_sink
        self.discarded_bytes = 0
        self.transport_separator_bytes = 0
        self.parsed_packets = 0
        self._after_packet = False

    def feed(self, data: bytes, host_time_ns: Optional[int] = None) -> List[ParsedPacket]:
        if not data:
            return []
        if self.raw_sink is not None:
            self.raw_sink.write(data)
        self.buffer.extend(data)
        packets: List[ParsedPacket] = []
        while True:
            # The custom firmware may append b"f\r\n" after each fixed packet.
            # Keep this state across arbitrary serial-read boundaries so a split
            # separator is not misreported as corrupt data.
            if self._after_packet:
                prefix_size = min(len(self.buffer), len(TRANSPORT_SEPARATOR))
                if prefix_size == 0:
                    break
                if bytes(self.buffer[:prefix_size]) == TRANSPORT_SEPARATOR[:prefix_size]:
                    if len(self.buffer) < len(TRANSPORT_SEPARATOR):
                        break
                    del self.buffer[: len(TRANSPORT_SEPARATOR)]
                    self.transport_separator_bytes += len(TRANSPORT_SEPARATOR)
                    self._after_packet = False
                    continue
                self._after_packet = False

            found = self._find_next_magic()
            if found is None:
                # Keep the last 7 bytes because they can be a partial magic word.
                keep = min(len(self.buffer), 7)
                drop = len(self.buffer) - keep
                if drop > 0:
                    self._drop_prefix(drop)
                break

            position, magic = found
            if position > 0:
                self._drop_prefix(position)

            if len(self.buffer) < self.packet_size:
                break

            # A complete packet begins at buffer[0].
            packet_bytes = bytes(self.buffer[: self.packet_size])
            del self.buffer[: self.packet_size]

            if packet_bytes[:8] != magic:
                # Defensive fallback; normally unreachable.
                self.discarded_bytes += 1
                self.buffer[:0] = packet_bytes[1:]
                continue

            # Do not assign one timestamp to every packet in a large serial read.
            # A single read can contain several radar frames.  The device timestamp
            # remains authoritative, but a per-packet host timestamp is still more
            # useful than a single timestamp copied across the whole chunk.
            timestamp_ns = int(time.time() * 1000000000) if host_time_ns is None else host_time_ns
            packets.append(self._parse_packet(packet_bytes, timestamp_ns))
            self.parsed_packets += 1
            self._after_packet = True

        return packets

    def finish(self) -> None:
        """Remove complete trailing transport separators after the final packet."""
        while self._after_packet and self.buffer.startswith(TRANSPORT_SEPARATOR):
            del self.buffer[: len(TRANSPORT_SEPARATOR)]
            self.transport_separator_bytes += len(TRANSPORT_SEPARATOR)
            self._after_packet = False

    def _drop_prefix(self, count: int) -> None:
        prefix = bytes(self.buffer[:count])
        del self.buffer[:count]
        self.discarded_bytes += len(prefix)

    def _find_next_magic(self) -> Optional[Tuple[int, bytes]]:
        best: Optional[Tuple[int, bytes]] = None
        for magic in MAGIC_WORDS:
            pos = self.buffer.find(magic)
            if pos >= 0 and (best is None or pos < best[0]):
                best = (pos, magic)
        return best

    def _parse_packet(self, packet: bytes, host_time_ns: int) -> ParsedPacket:
        magic = packet[:8]
        antenna_id = MAGIC_TO_ANTENNA[magic]
        device_timestamp = struct.unpack_from("<I", packet, 8)[0]

        # Firmware stores each range bin as Q(int16), I(int16).
        interleaved_qi = np.frombuffer(
            packet,
            dtype="<i2",
            count=self.range_bins * 2,
            offset=12,
        ).reshape(self.range_bins, 2)
        iq = interleaved_qi[:, ::-1].copy()  # convert [Q,I] -> [I,Q]

        return ParsedPacket(
            antenna_id=antenna_id,
            device_timestamp=device_timestamp,
            iq=iq,
            host_time_ns=host_time_ns,
        )


class FrameAssembler:
    """Combines four ordered antenna packets into one radar frame."""

    def __init__(self, antenna_count: int = 4, range_bins: int = 20):
        self.antenna_count = antenna_count
        self.range_bins = range_bins
        self._packets: Dict[int, ParsedPacket] = {}
        self._frame_id = 0
        self.incomplete_frames = 0
        self.out_of_order_packets = 0
        self.duplicate_packets = 0

    def add(self, packet: ParsedPacket) -> Optional[CompletedFrame]:
        ant = packet.antenna_id
        if ant >= self.antenna_count:
            return None

        # Antenna 0 marks the beginning of a frame in the existing protocol.
        if ant == 0 and self._packets:
            self.incomplete_frames += 1
            self._packets.clear()

        expected = len(self._packets)
        if ant != expected:
            self.out_of_order_packets += 1
            if ant in self._packets:
                self.duplicate_packets += 1
            # Resynchronize only at antenna 0.
            if ant != 0:
                return None
            self._packets.clear()

        self._packets[ant] = packet
        if len(self._packets) < self.antenna_count:
            return None

        ordered = [self._packets[i] for i in range(self.antenna_count)]
        iq = np.stack([p.iq for p in ordered], axis=0)
        frame = CompletedFrame(
            frame_id=self._frame_id,
            host_time_ns=ordered[0].host_time_ns,
            device_timestamps=tuple(p.device_timestamp for p in ordered),
            iq=iq,
        )
        self._frame_id += 1
        self._packets.clear()
        return frame

    def finish(self) -> None:
        """Account for a partial frame left when acquisition stops."""
        if self._packets:
            self.incomplete_frames += 1
            self._packets.clear()


class WideCsvFrameWriter:
    """Buffered lossless CSV writer: one row per frame, integer I/Q values."""

    def __init__(
        self,
        session_dir: Path,
        metadata: CaptureMetadata,
        flush_every_frames: int = 100,
        rotate_every_frames: int = 60_000,
    ):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.metadata = metadata
        self.flush_every_frames = max(1, flush_every_frames)
        self.rotate_every_frames = max(1, rotate_every_frames)
        self._file: Optional[TextIO] = None
        self._writer: Optional[csv.writer] = None
        self._part_index = -1
        self._part_frames = 0
        self.total_frames = 0
        self._open_next_part()

    @property
    def header(self) -> List[str]:
        columns = ["frame_id", "host_time_ns", "host_time_iso_utc"]
        columns += [f"device_ts_a{a + 1}" for a in range(self.metadata.antenna_count)]
        for ant in range(self.metadata.antenna_count):
            for bin_idx in range(self.metadata.range_bins):
                columns.extend(
                    [f"a{ant + 1}_b{bin_idx:02d}_i", f"a{ant + 1}_b{bin_idx:02d}_q"]
                )
        return columns

    def write(self, frame: CompletedFrame) -> None:
        if self._writer is None or self._file is None:
            raise RuntimeError("CSV writer is closed")
        if frame.iq.shape != (
            self.metadata.antenna_count,
            self.metadata.range_bins,
            2,
        ):
            raise ValueError(f"unexpected frame shape: {frame.iq.shape}")

        if self._part_frames >= self.rotate_every_frames:
            self._open_next_part()

        host_iso = datetime.fromtimestamp(
            frame.host_time_ns / 1_000_000_000, tz=timezone.utc
        ).isoformat(timespec="microseconds")
        row: List[object] = [frame.frame_id, frame.host_time_ns, host_iso]
        row.extend(frame.device_timestamps)
        row.extend(frame.iq.reshape(-1).astype(np.int16).tolist())
        self._writer.writerow(row)

        self._part_frames += 1
        self.total_frames += 1
        if self.total_frames % self.flush_every_frames == 0:
            self._file.flush()

    def _open_next_part(self) -> None:
        self.close_current_part()
        self._part_index += 1
        self._part_frames = 0
        label = f"_{self.metadata.file_label}" if self.metadata.file_label else ""
        path = self.session_dir / (
            f"range_fft_iq{label}_part_{self._part_index:04d}.csv"
        )
        self._file = path.open("w", newline="", encoding="utf-8", buffering=1024 * 1024)
        self._writer = csv.writer(self._file, lineterminator="\n")
        self._writer.writerow(self.header)
        self._file.flush()

    def close_current_part(self) -> None:
        if self._file is not None:
            self._file.flush()
            try:
                os.fsync(self._file.fileno())
            except OSError:
                pass
            self._file.close()
        self._file = None
        self._writer = None

    def close(self) -> None:
        self.close_current_part()


def create_session_directory(output_root: Path, session_id: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_session = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in session_id)
    session_dir = Path(output_root) / f"{timestamp}_{safe_session}"
    session_dir.mkdir(parents=True, exist_ok=False)
    return session_dir


def write_metadata(path: Path, metadata: CaptureMetadata, extra: Optional[dict] = None) -> None:
    payload = dict(metadata.__dict__)
    if extra:
        payload.update(extra)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_summary(path: Path, **stats: object) -> None:
    path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
