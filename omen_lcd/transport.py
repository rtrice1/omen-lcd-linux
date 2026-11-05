"""Display-only Linux hidraw transport; no vendor libraries are loaded."""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
from io import BytesIO
import math
import os
import signal
import stat
import struct
import threading
import time

from PIL import Image

from .device import Device, DeviceError, PRODUCT_ID, REPORT_DESCRIPTOR, VENDOR_ID, identify_device
from .protocol import MAX_IMAGE_BYTES, image_reports

HIDIOCGRAWINFO = 0x80084803
HIDIOCGRDESCSIZE = 0x80044801
HIDIOCGRDESC = 0x90044802


def validate_frame(jpeg: bytes) -> None:
    if not isinstance(jpeg, bytes) or not 0 < len(jpeg) <= MAX_IMAGE_BYTES:
        raise ValueError(f"JPEG must contain 1–{MAX_IMAGE_BYTES} bytes")
    try:
        with Image.open(BytesIO(jpeg)) as image:
            if image.format != "JPEG" or image.size != (480, 480) or image.mode != "RGB":
                raise ValueError("LCD requires a 480×480 RGB JPEG")
            if image.info.get("progressive") or image.info.get("progression"):
                raise ValueError("LCD requires a baseline JPEG")
            image.load()
    except (OSError, Image.DecompressionBombError) as error:
        raise ValueError(f"Invalid JPEG: {error}") from error


@contextmanager
def _deadline(seconds: float):
    """Interrupt a stalled, interruptible syscall in this dedicated CLI process."""
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("LCD transfers must run on the main thread")
    if signal.getitimer(signal.ITIMER_REAL)[0] > 0:
        raise RuntimeError("An existing process alarm conflicts with LCD transfer timing")
    previous = signal.getsignal(signal.SIGALRM)

    def expired(signum, frame):
        raise TimeoutError("LCD frame transfer timed out; no retry was attempted")

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


class HidrawDisplay:
    """Hold an exclusive cooperative lock and send only live-image reports.

    A successful write means the kernel accepted the reports. This protocol path
    provides no application acknowledgement or proof of physical appearance.
    """

    def __init__(self, device: Device):
        self.device = device
        self.fd: int | None = None
        self.failed = False

    def __enter__(self):
        # Recheck cached metadata immediately before opening the current node.
        checked = identify_device(self.device.node)
        if checked != self.device:
            raise DeviceError("LCD identity changed before access")
        fd = os.open(self.device.node, os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            if not stat.S_ISCHR(os.fstat(fd).st_mode):
                raise DeviceError("LCD node is not a character device")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            info = bytearray(8)
            fcntl.ioctl(fd, HIDIOCGRAWINFO, info, True)
            if struct.unpack("<IHH", info) != (3, VENDOR_ID, PRODUCT_ID):
                raise DeviceError("Opened HID device has the wrong USB identity")
            size = bytearray(4)
            fcntl.ioctl(fd, HIDIOCGRDESCSIZE, size, True)
            if struct.unpack("<I", size)[0] != len(REPORT_DESCRIPTOR):
                raise DeviceError("Opened HID report size changed")
            descriptor = bytearray(4100)
            struct.pack_into("<I", descriptor, 0, len(REPORT_DESCRIPTOR))
            fcntl.ioctl(fd, HIDIOCGRDESC, descriptor, True)
            actual_size = struct.unpack_from("<I", descriptor)[0]
            if actual_size != len(REPORT_DESCRIPTOR) or descriptor[4 : 4 + actual_size] != REPORT_DESCRIPTOR:
                raise DeviceError("Opened HID report descriptor changed")
        except BaseException:
            os.close(fd)
            raise
        self.fd = fd
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def send_frame(self, jpeg: bytes, *, timeout: float = 5.0) -> int:
        validate_frame(jpeg)
        if self.fd is None or self.failed:
            raise DeviceError("LCD connection is closed or failed; reopen it before another transfer")
        if not math.isfinite(timeout) or not 0.1 <= timeout <= 30:
            raise ValueError("Transfer timeout must be 0.1–30 seconds")
        count = 0
        try:
            with _deadline(timeout):
                until = time.monotonic() + timeout
                for report in image_reports(jpeg):
                    if time.monotonic() >= until:
                        raise TimeoutError("LCD frame deadline exceeded")
                    written = os.write(self.fd, report)
                    if written != len(report):
                        raise OSError(f"Short LCD report write: {written}/{len(report)}; transfer stopped")
                    count += 1
        except BaseException:
            self.failed = True
            raise
        return count
