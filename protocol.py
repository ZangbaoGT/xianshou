"""16-byte event packet used by the "First Move" demo.

Packet layout (network byte order):

    timestamp_ms   uint32   4 B   sender clock, ms
    src_id         uint8    1 B   robot id
    event_type     uint8    1 B   1=obstacle, 2=neighbor, 3=formation, 4=heartbeat
    bearing_deg    uint16   2 B   ＊10, 0..3599  (0.1 degree resolution)
    distance_cm    uint16   2 B   0..65535
    confidence     uint8    1 B   0..100
    seq            uint8    1 B   wraps at 256
    reserved       uint16   2 B   future flags / hop count
    crc16          uint16   2 B   CRC-16/CCITT over the first 14 bytes
                  ------
                  16 B
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

PACKET_FORMAT = "!IBBHHBBHH"
PACKET_SIZE = struct.calcsize(PACKET_FORMAT)
assert PACKET_SIZE == 16, PACKET_SIZE

EVENT_TYPES = {
    "obstacle": 1,
    "neighbor": 2,
    "formation": 3,
    "heartbeat": 4,
}

EVENT_NAMES = {v: k for k, v in EVENT_TYPES.items()}


def crc16_ccitt(data: bytes, crc: int = 0xFFFF) -> int:
    """CRC-16/CCITT-FALSE, the same polynomial used by many radio stacks."""
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


@dataclass
class EventPacket:
    timestamp_ms: int
    src_id: int
    event_type: int
    bearing_deg: float
    distance_cm: int
    confidence: float
    seq: int
    reserved: int = 0

    def encode(self) -> bytes:
        bearing = int(round((self.bearing_deg % 360.0) * 10.0)) % 3600
        confidence = max(0, min(100, int(round(self.confidence * 100.0))))
        distance = max(0, min(65535, int(self.distance_cm)))
        head = struct.pack(
            "!IBBHHBBH",
            self.timestamp_ms & 0xFFFFFFFF,
            self.src_id & 0xFF,
            self.event_type & 0xFF,
            bearing,
            distance,
            confidence,
            self.seq & 0xFF,
            self.reserved & 0xFFFF,
        )
        return head + struct.pack("!H", crc16_ccitt(head))

    @classmethod
    def decode(cls, data: bytes) -> "EventPacket":
        if len(data) != PACKET_SIZE:
            raise ValueError(f"expected {PACKET_SIZE} bytes, got {len(data)}")
        head, crc = data[:-2], struct.unpack("!H", data[-2:])[0]
        if crc16_ccitt(head) != crc:
            raise ValueError("crc mismatch")
        ts, src, typ, bearing, dist, conf, seq, reserved = struct.unpack(
            "!IBBHHBBH", head
        )
        return cls(
            timestamp_ms=ts,
            src_id=src,
            event_type=typ,
            bearing_deg=bearing / 10.0,
            distance_cm=dist,
            confidence=conf / 100.0,
            seq=seq,
            reserved=reserved,
        )

    def __str__(self) -> str:
        name = EVENT_NAMES.get(self.event_type, str(self.event_type))
        return (
            f"src={self.src_id} type={name} bearing={self.bearing_deg:.1f}deg "
            f"dist={self.distance_cm}cm conf={self.confidence:.2f} seq={self.seq}"
        )


if __name__ == "__main__":
    pkt = EventPacket(123456, 1, EVENT_TYPES["obstacle"], 42.5, 180, 0.93, 7)
    raw = pkt.encode()
    print(f"encoded {len(raw)} bytes: {raw.hex()}")
    print("decoded:", EventPacket.decode(raw))
