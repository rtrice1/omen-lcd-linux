from pathlib import Path

import pytest

from omen_lcd.device import DeviceError, REPORT_DESCRIPTOR, discover_devices, identify_device


@pytest.fixture
def usb_tree(tmp_path):
    dev = tmp_path / "dev"
    dev.mkdir()
    node = dev / "hidraw5"
    node.touch()
    usb = tmp_path / "usb" / "1-10"
    interface = usb / "1-10:1.1"
    hid = interface / "0003:03F0:7397.0006"
    hid.mkdir(parents=True)
    (usb / "idVendor").write_text("03f0\n")
    (usb / "idProduct").write_text("7397\n")
    (interface / "bInterfaceNumber").write_text("01\n")
    (hid / "report_descriptor").write_bytes(REPORT_DESCRIPTOR)
    sysfs = tmp_path / "class"
    (sysfs / "hidraw5").mkdir(parents=True)
    (sysfs / "hidraw5" / "device").symlink_to(hid)
    return node, dev, sysfs, usb, interface, hid


def test_finds_only_matching_interface(usb_tree):
    node, dev, sysfs, *_ = usb_tree
    result = discover_devices(sysfs_root=sysfs, dev_root=dev)
    assert [d.node for d in result] == [node]


@pytest.mark.parametrize("attribute,value", [("vendor", "0416"), ("product", "7395"), ("interface", "00"), ("descriptor", b"mouse")])
def test_rejects_other_usb_ids_mouse_interface_and_descriptor(usb_tree, attribute, value):
    node, dev, sysfs, usb, interface, hid = usb_tree
    if attribute == "descriptor":
        (hid / "report_descriptor").write_bytes(value)
    else:
        path = {"vendor": usb / "idVendor", "product": usb / "idProduct", "interface": interface / "bInterfaceNumber"}[attribute]
        path.write_text(value)
    with pytest.raises(DeviceError):
        identify_device(node, sysfs_root=sysfs, dev_root=dev)
    assert discover_devices(sysfs_root=sysfs, dev_root=dev) == []


def test_rejects_node_outside_dev_root(usb_tree, tmp_path):
    _, dev, sysfs, *_ = usb_tree
    other = tmp_path / "hidraw5"
    other.touch()
    with pytest.raises(DeviceError):
        identify_device(other, sysfs_root=sysfs, dev_root=dev)
