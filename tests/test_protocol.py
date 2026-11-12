import unittest

from protocol import PACKET_SIZE, EventPacket, crc16_ccitt


class TestProtocol(unittest.TestCase):
    def test_packet_size_is_16(self):
        self.assertEqual(PACKET_SIZE, 16)

    def test_roundtrip(self):
        packet = EventPacket(
            timestamp_ms=123456,
            src_id=2,
            event_type=1,
            bearing_deg=42.5,
            distance_cm=180,
            confidence=0.93,
            seq=7,
            reserved=0,
        )
        raw = packet.encode()
        self.assertEqual(len(raw), 16)
        decoded = EventPacket.decode(raw)
        self.assertEqual(decoded.timestamp_ms, 123456)
        self.assertEqual(decoded.src_id, 2)
        self.assertEqual(decoded.event_type, 1)
        self.assertAlmostEqual(decoded.bearing_deg, 42.5, places=1)
        self.assertEqual(decoded.distance_cm, 180)
        self.assertAlmostEqual(decoded.confidence, 0.93, places=2)
        self.assertEqual(decoded.seq, 7)

    def test_bearing_wraps(self):
        packet = EventPacket(1, 1, 1, 359.96, 0, 1.0, 0)
        decoded = EventPacket.decode(packet.encode())
        self.assertAlmostEqual(decoded.bearing_deg, 0.0, delta=0.1)

    def test_crc_detects_corruption(self):
        raw = bytearray(EventPacket(1, 1, 1, 10.0, 100, 0.5, 0).encode())
        raw[0] ^= 0xFF
        with self.assertRaises(ValueError):
            EventPacket.decode(bytes(raw))

    def test_rejects_wrong_length(self):
        with self.assertRaises(ValueError):
            EventPacket.decode(b"\x00" * 15)

    def test_crc_check_value(self):
        # CRC-16/CCITT-FALSE check value
        self.assertEqual(crc16_ccitt(b"123456789"), 0x29B1)


if __name__ == "__main__":
    unittest.main()
