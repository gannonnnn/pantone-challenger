import io

from PIL import Image, ImageDraw

from challenger.capture import _normalise_logo_bytes


def test_logo_normalisation_creates_consistent_transparent_asset(tmp_path):
    source = Image.new("RGB", (400, 160), "white")
    draw = ImageDraw.Draw(source)
    draw.rectangle((80, 50, 320, 110), fill="#1A1A1A")
    payload = io.BytesIO()
    source.save(payload, format="PNG")

    output = tmp_path / "logo.png"
    assert _normalise_logo_bytes(payload.getvalue(), output)

    logo = Image.open(output).convert("RGBA")
    assert logo.size == (260, 128)
    assert logo.getchannel("A").getbbox() is not None
