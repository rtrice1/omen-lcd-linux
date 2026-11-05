import pytest

from omen_lcd.protocol import MAX_IMAGE_BYTES, image_reports


def test_two_packets_match_observed_wire_layout():
    packets = list(image_reports(b"A" * 1013 + b"B"))
    assert len(packets) == 2
    assert packets[0] == bytes.fromhex("026e000003f600000003f5") + b"A" * 1013
    assert packets[1] == (bytes.fromhex("026e000003f60000010001") + b"B").ljust(1024, b"\0")


@pytest.mark.parametrize("length,expected", [(1, 1), (1012, 1), (1013, 1), (1014, 2), (2026, 2)])
def test_boundaries_and_reassembly(length, expected):
    data = bytes(i % 251 for i in range(length))
    packets = list(image_reports(data))
    assert len(packets) == expected
    restored = b""
    for index, packet in enumerate(packets):
        assert len(packet) == 1024
        assert packet[:2] == b"\x02\x6e"
        assert int.from_bytes(packet[2:6], "big") == length
        assert int.from_bytes(packet[6:9], "big") == index
        size = int.from_bytes(packet[9:11], "big")
        assert 1 <= size <= 1013
        restored += packet[11:11 + size]
        assert packet[11 + size:] == bytes(1013 - size)
    assert restored == data


@pytest.mark.parametrize("data", [b"", bytes(MAX_IMAGE_BYTES + 1), bytearray(b"A")])
def test_rejects_invalid_size_or_mutable_input(data):
    with pytest.raises((ValueError, TypeError)):
        list(image_reports(data))
