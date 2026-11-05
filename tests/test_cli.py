import signal
from unittest.mock import patch

from omen_lcd import __main__ as cli


def test_preview_never_opens_usb(tmp_path):
    output = tmp_path / "preview.jpg"
    with patch.object(cli, "HidrawDisplay") as hardware, \
         patch.object(cli, "read_temperatures", return_value={"cpu_c": None, "gpu_c": None}):
        assert cli.main(["preview", str(output)]) == 0
        hardware.assert_not_called()
    assert output.read_bytes().startswith(b"\xff\xd8")


def test_invalid_interval_fails_before_device_access():
    with patch.object(cli, "HidrawDisplay") as hardware:
        assert cli.main(["run", "--interval", "nan"]) == 1
        hardware.assert_not_called()


def test_sigterm_replaces_retained_values_and_restores_handlers():
    previous_term = signal.getsignal(signal.SIGTERM)
    previous_int = signal.getsignal(signal.SIGINT)
    rendered = []

    class FakeDisplay:
        failed = False
        device = type("Device", (), {"node": "/dev/hidraw-test"})()

        def __init__(self, device):
            self.frames = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def send_frame(self, image):
            self.frames += 1
            if self.frames == 1:
                signal.raise_signal(signal.SIGTERM)
            return 1

    with patch.object(cli, "HidrawDisplay", FakeDisplay), \
         patch.object(cli, "choose_device", return_value=object()), \
         patch.object(cli, "read_temperatures", return_value={"cpu_c": 67.0, "gpu_c": 71.0}), \
         patch.object(cli, "render_dashboard", side_effect=lambda cpu, gpu: rendered.append((cpu, gpu)) or b"jpeg"):
        assert cli.main(["run", "--interval", "1"]) == 0
    assert rendered == [(67.0, 71.0), (None, None)]
    assert signal.getsignal(signal.SIGTERM) == previous_term
    assert signal.getsignal(signal.SIGINT) == previous_int
