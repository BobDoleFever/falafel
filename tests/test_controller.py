from pathlib import Path

from bnet_umu.core import controller


def test_find_virtual_gamepad_detects_steam_input_device(tmp_path):
    devices_path = tmp_path / "devices"
    devices_path.write_text(
        "I: Bus=0003 Vendor=045e Product=028e Version=0110\n"
        'N: Name="Some Real Controller"\n'
        "P: Phys=usb-0000:00:14.0-1/input0\n"
        "\n"
        "I: Bus=0000 Vendor=045e Product=028e Version=0000\n"
        'N: Name="Microsoft X-Box 360 pad 0"\n'
        "P: Phys=\n"
        "S: Sysfs=/devices/virtual/input/input45\n"
        "H: Handlers=event13 js0 \n"
    )

    assert controller.find_virtual_gamepad(devices_path) == "Microsoft X-Box 360 pad 0"


def test_find_virtual_gamepad_returns_none_when_absent(tmp_path):
    devices_path = tmp_path / "devices"
    devices_path.write_text(
        "I: Bus=0003 Vendor=045e Product=028e Version=0110\n"
        'N: Name="Some Real Controller"\n'
    )

    assert controller.find_virtual_gamepad(devices_path) is None


def test_find_virtual_gamepad_returns_none_when_file_missing(tmp_path):
    assert controller.find_virtual_gamepad(tmp_path / "nope") is None
