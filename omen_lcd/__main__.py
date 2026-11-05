"""Command line entry point for passive previews and the HP LCD display."""

from __future__ import annotations

import argparse
from io import BytesIO
import json
import logging
import math
from pathlib import Path
import signal
import sys
import threading

from PIL import Image

from .device import DeviceError, choose_device, discover_devices
from .protocol import MAX_IMAGE_BYTES
from .render import render_dashboard
from .sensors import read_temperatures
from .transport import HidrawDisplay

LOG = logging.getLogger("omen_lcd")


def _jpeg_from_file(path: Path) -> bytes:
    with path.open("rb") as source:
        data = source.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Input image exceeds 512 KiB")
    with Image.open(BytesIO(data)) as image:
        if image.format != "JPEG" or image.size != (480, 480):
            raise ValueError("Choose a 480×480 JPEG image")
        output = BytesIO()
        image.convert("RGB").save(output, format="JPEG", quality=92, optimize=True)
        return output.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live temperatures on the HP OMEN cooler LCD")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List supported LCD interfaces without opening them")
    preview = commands.add_parser("preview", help="Save a live-temperature JPEG without accessing USB")
    preview.add_argument("file", type=Path)
    show = commands.add_parser("show", help="Send one 480×480 JPEG to the physical LCD")
    show.add_argument("file", type=Path)
    show.add_argument("--device")
    run = commands.add_parser("run", help="Refresh the physical LCD with live temperatures")
    run.add_argument("--device")
    run.add_argument("--interval", type=float, default=2.0, help="Seconds between updates (minimum 1)")
    run.add_argument("--frames", type=int, help="Stop after this many frames, for a bounded hardware test")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        if args.command == "list":
            print(json.dumps([{"device": str(d.node), "usb": "03f0:7397", "interface": 1} for d in discover_devices()], indent=2))
            return 0
        if args.command == "preview":
            readings = read_temperatures()
            args.file.write_bytes(render_dashboard(readings["cpu_c"], readings["gpu_c"]))
            print(json.dumps({"image": str(args.file), **readings}))
            return 0
        if args.command == "run":
            if not math.isfinite(args.interval) or not 1 <= args.interval <= 3600:
                raise ValueError("Update interval must be 1–3600 seconds")
            if args.frames is not None and args.frames < 1:
                raise ValueError("Frame count must be positive")
        stop = threading.Event()

        def stopping(signum, frame):
            stop.set()

        old_term = signal.signal(signal.SIGTERM, stopping)
        old_int = signal.signal(signal.SIGINT, stopping)
        try:
            image_to_show = _jpeg_from_file(args.file) if args.command == "show" else None
            with HidrawDisplay(choose_device(args.device)) as display:
                if args.command == "show":
                    count = display.send_frame(image_to_show)
                    LOG.info("Sent one image in %s reports; physical appearance requires observation", count)
                    return 0
                sent = 0
                while not stop.is_set():
                    readings = read_temperatures()
                    display.send_frame(render_dashboard(readings["cpu_c"], readings["gpu_c"]))
                    sent += 1
                    if sent == 1:
                        LOG.info("Sending temperature frames to %s every %.1fs", display.device.node, args.interval)
                    if args.frames is not None and sent >= args.frames:
                        break
                    stop.wait(args.interval)
                if stop.is_set() and not display.failed:
                    # Replace retained readings with unavailable values on a normal stop.
                    # No undocumented blanking or persistent configuration command is used.
                    try:
                        display.send_frame(render_dashboard(None, None))
                    except (OSError, ValueError, RuntimeError):
                        LOG.warning("Could not replace the last frame during shutdown")
        finally:
            signal.signal(signal.SIGTERM, old_term)
            signal.signal(signal.SIGINT, old_int)
        return 0
    except PermissionError:
        LOG.error("LCD permission denied. Install the service/udev rule or run the one-time hardware test with sudo.")
    except (DeviceError, OSError, ValueError, RuntimeError) as error:
        LOG.error("%s", error)
    return 1


if __name__ == "__main__":
    sys.exit(main())
