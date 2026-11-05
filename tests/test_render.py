from io import BytesIO

from PIL import Image

from omen_lcd.render import _display_value, _footer_text, render_dashboard


def test_render_is_480_square_jpeg():
    image = Image.open(BytesIO(render_dashboard(67.5, 51.0)))
    assert image.format == "JPEG"
    assert image.size == (480, 480)


def test_missing_sensor_does_not_become_zero():
    data = render_dashboard(None, None)
    assert _display_value(None) == "--"
    assert _display_value(0.0) == "0.0°C"
    assert _footer_text(None, None) == "SENSORS UNAVAILABLE"
    assert _footer_text(0.0, None).startswith("UPDATED ")
    image = Image.open(BytesIO(data))
    assert image.size == (480, 480)
