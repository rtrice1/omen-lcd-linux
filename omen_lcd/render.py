"""Generate a display-only 480x480 dashboard image."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 480
_FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    paths = (_FONT_PATHS[1], _FONT_PATHS[0]) if bold else _FONT_PATHS
    for path in paths:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default()


def _display_value(value: float | None) -> str:
    return "--" if value is None else f"{value:.1f}°C"


def _footer_text(cpu_c: float | None, gpu_c: float | None) -> str:
    if cpu_c is None and gpu_c is None:
        return "SENSORS UNAVAILABLE"
    return "UPDATED " + datetime.now(timezone.utc).strftime("%H:%M:%S UTC")


def _centered(draw: ImageDraw.ImageDraw, center: tuple[int, int], text: str, font: ImageFont.ImageFont, fill: tuple[int, int, int]) -> None:
    box = draw.textbbox((0, 0), text, font=font)
    x = center[0] - (box[2] - box[0]) // 2
    y = center[1] - (box[3] - box[1]) // 2 - box[1]
    draw.text((x, y), text, font=font, fill=fill)


def render_dashboard(cpu_c: float | None, gpu_c: float | None) -> bytes:
    """Render two temperature cards inside a circular 480x480 display."""
    image = Image.new("RGB", (SIZE, SIZE), (10, 14, 22))
    draw = ImageDraw.Draw(image)
    circle = (8, 8, SIZE - 8, SIZE - 8)
    draw.ellipse(circle, fill=(18, 26, 39), outline=(78, 99, 124), width=3)
    draw.arc((28, 28, SIZE - 28, SIZE - 28), 205, 335, fill=(43, 177, 218), width=6)
    draw.arc((28, 28, SIZE - 28, SIZE - 28), 25, 155, fill=(242, 157, 63), width=6)

    label_font = _font(25, bold=True)
    value_font = _font(59, bold=True)
    muted = (164, 181, 201)
    white = (238, 245, 252)
    _centered(draw, (240, 151), "CPU", label_font, (87, 204, 236))
    _centered(draw, (240, 211), _display_value(cpu_c), value_font, white)
    _centered(draw, (240, 286), "GPU", label_font, (255, 181, 91))
    _centered(draw, (240, 346), _display_value(gpu_c), value_font, white)
    footer = _footer_text(cpu_c, gpu_c)
    _centered(draw, (240, 414), footer, _font(14), muted)

    output = BytesIO()
    image.save(output, format="JPEG", quality=92, optimize=True)
    return output.getvalue()
