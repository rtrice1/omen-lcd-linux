from pathlib import Path
import signal
import stat
import struct
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from omen_lcd.device import Device, DeviceError, REPORT_DESCRIPTOR
from omen_lcd.render import render_dashboard
from omen_lcd.transport import HIDIOCGRAWINFO, HIDIOCGRDESC, HIDIOCGRDESCSIZE, HidrawDisplay


@pytest.fixture
def jpeg():
    return render_dashboard(65.0, 73.0)


@pytest.fixture
def connection():
    device = Device(Path("/dev/hidraw5"), Path("/sys/fake"))

    def ioctl(fd, request, buffer, mutate):
        if request == HIDIOCGRAWINFO:
            buffer[:] = struct.pack("<IHH", 3, 0x03F0, 0x7397)
        elif request == HIDIOCGRDESCSIZE:
            buffer[:] = struct.pack("<I", len(REPORT_DESCRIPTOR))
        elif request == HIDIOCGRDESC:
            buffer[4:4 + len(REPORT_DESCRIPTOR)] = REPORT_DESCRIPTOR
        else:
            raise AssertionError("Unexpected HID request")

    with patch("omen_lcd.transport.identify_device", return_value=device), \
         patch("omen_lcd.transport.os.open", return_value=42), \
         patch("omen_lcd.transport.os.fstat", return_value=SimpleNamespace(st_mode=stat.S_IFCHR)), \
         patch("omen_lcd.transport.os.close") as close, \
         patch("omen_lcd.transport.fcntl.flock") as lock, \
         patch("omen_lcd.transport.fcntl.ioctl", side_effect=ioctl) as io:
        yield device, close, lock, io


def test_sends_only_image_reports_and_closes(connection, jpeg):
    device, close, lock, _ = connection
    reports = []
    with patch("omen_lcd.transport.os.write", side_effect=lambda fd, report: reports.append(report) or len(report)):
        with HidrawDisplay(device) as display:
            assert display.send_frame(jpeg) == len(reports)
    assert reports and all(len(p) == 1024 and p[:2] == b"\x02\x6e" for p in reports)
    lock.assert_called_once()
    close.assert_called_once_with(42)


def test_short_write_fails_without_retry_and_poisons_connection(connection, jpeg):
    device, *_ = connection
    with HidrawDisplay(device) as display, patch("omen_lcd.transport.os.write", return_value=12) as write:
        with pytest.raises(OSError, match="Short LCD"):
            display.send_frame(jpeg)
        with pytest.raises(DeviceError, match="failed"):
            display.send_frame(jpeg)
        assert write.call_count == 1


def test_device_identity_change_closes_without_write(connection):
    device, close, _, io = connection
    io.side_effect = lambda fd, req, buf, mutate: buf.__setitem__(slice(None), bytes(len(buf)))
    with patch("omen_lcd.transport.os.write") as write:
        with pytest.raises(DeviceError, match="identity"):
            with HidrawDisplay(device):
                pass
        write.assert_not_called()
    close.assert_called_once_with(42)


def test_second_owner_rejected(connection):
    device, close, lock, _ = connection
    lock.side_effect = BlockingIOError("already owned")
    with pytest.raises(BlockingIOError):
        with HidrawDisplay(device):
            pass
    close.assert_called_once_with(42)


def test_frame_alarm_interrupts_stalled_call_and_is_restored(connection, jpeg):
    device, *_ = connection
    old = signal.getsignal(signal.SIGALRM)
    with HidrawDisplay(device) as display, patch("omen_lcd.transport.os.write", side_effect=lambda *args: time.sleep(0.4)):
        with pytest.raises(TimeoutError):
            display.send_frame(jpeg, timeout=0.1)
        assert display.failed
    assert signal.getsignal(signal.SIGALRM) == old
    assert signal.getitimer(signal.ITIMER_REAL)[0] == 0


def test_invalid_frame_never_writes(connection):
    device, *_ = connection
    with HidrawDisplay(device) as display, patch("omen_lcd.transport.os.write") as write:
        with pytest.raises(ValueError):
            display.send_frame(b"not an image")
        write.assert_not_called()
