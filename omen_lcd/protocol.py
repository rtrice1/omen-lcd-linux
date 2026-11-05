"""Original encoder for the HP LCD's observed live-image report format.

Only the image synchronization operation is implemented. See docs/protocol-analysis.md.
"""

from __future__ import annotations

from collections.abc import Iterator

REPORT_SIZE = 1024
PAYLOAD_SIZE = 1013
MAX_IMAGE_BYTES = 512 * 1024


def image_reports(jpeg: bytes) -> Iterator[bytes]:
    """Encode one image as numbered reports, including the HID report ID.

    This conservative size limit is a project limit, not an inferred device limit.
    JPEG decoding/dimension validation belongs to the display boundary.
    """
    if not isinstance(jpeg, bytes):
        raise TypeError("Image data must be immutable bytes")
    length = len(jpeg)
    if not 0 < length <= MAX_IMAGE_BYTES:
        raise ValueError(f"Image must contain 1–{MAX_IMAGE_BYTES} bytes")
    for index, offset in enumerate(range(0, length, PAYLOAD_SIZE)):
        chunk = jpeg[offset : offset + PAYLOAD_SIZE]
        header = (
            b"\x02\x6e"
            + length.to_bytes(4, "big")
            + index.to_bytes(3, "big")
            + len(chunk).to_bytes(2, "big")
        )
        yield (header + chunk).ljust(REPORT_SIZE, b"\x00")
