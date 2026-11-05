"""Discover only the supported HP LCD interface from cached kernel metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

VENDOR_ID = 0x03F0
PRODUCT_ID = 0x7397
INTERFACE_NUMBER = 1
# Cached descriptor observed on the supported LCD-PUMP interface, not its mouse interface.
REPORT_DESCRIPTOR = bytes.fromhex(
    "061aff0993a101850119002aff00150026ff007508953f8102190029ff9102"
    "0993850219002aff00150026ff00750896ff01810296ff03190029ff9102c0"
)


class DeviceError(RuntimeError):
    """The requested device is unavailable or outside the supported boundary."""


@dataclass(frozen=True)
class Device:
    node: Path
    sysfs_device: Path


def identify_device(
    node: Path,
    *,
    sysfs_root: Path = Path("/sys/class/hidraw"),
    dev_root: Path = Path("/dev"),
) -> Device:
    """Check USB identity, interface number and exact cached report descriptor."""
    try:
        resolved = node.resolve(strict=True)
        if resolved.parent != dev_root.resolve() or not re.fullmatch(r"hidraw[0-9]+", resolved.name):
            raise DeviceError("Choose a hidraw device under /dev")
        hid = (sysfs_root / resolved.name / "device").resolve(strict=True)
        interface = next(p for p in hid.parents if (p / "bInterfaceNumber").is_file())
        usb = next(p for p in interface.parents if (p / "idVendor").is_file())
        identity = (
            int((usb / "idVendor").read_text().strip(), 16),
            int((usb / "idProduct").read_text().strip(), 16),
            int((interface / "bInterfaceNumber").read_text().strip(), 16),
        )
        if identity != (VENDOR_ID, PRODUCT_ID, INTERFACE_NUMBER):
            raise DeviceError("Device is not HP 03f0:7397 display interface 1")
        if (hid / "report_descriptor").read_bytes() != REPORT_DESCRIPTOR:
            raise DeviceError("LCD report descriptor is unrecognized; refusing access")
        return Device(resolved, hid)
    except (OSError, ValueError, StopIteration) as error:
        raise DeviceError(f"Cannot identify supported LCD: {error}") from error


def discover_devices(
    *, sysfs_root: Path = Path("/sys/class/hidraw"), dev_root: Path = Path("/dev")
) -> list[Device]:
    devices = []
    for candidate in sorted(sysfs_root.glob("hidraw*")):
        try:
            devices.append(identify_device(dev_root / candidate.name, sysfs_root=sysfs_root, dev_root=dev_root))
        except DeviceError:
            continue
    return devices


def choose_device(node: str | None = None) -> Device:
    if node is not None:
        return identify_device(Path(node))
    devices = discover_devices()
    if len(devices) != 1:
        raise DeviceError(f"Expected one supported LCD, found {len(devices)}; use 'omen-lcd list'")
    return devices[0]
