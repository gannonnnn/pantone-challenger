from PIL import Image, ImageDraw

from challenger.image_quality import image_rejection_reason, text_looks_like_overlay, trim_and_fit_logo


def test_blank_region_rejected(tmp_path):
    path = tmp_path / "blank.png"
    Image.new("RGB", (600, 400), "white").save(path)
    assert image_rejection_reason(path) in {"nearly_blank_region", "low_information_placeholder", "flat_placeholder"}


def test_real_visual_region_is_kept(tmp_path):
    path = tmp_path / "visual.png"
    image = Image.new("RGB", (600, 400), "#A5C84A")
    draw = ImageDraw.Draw(image)
    draw.ellipse((100, 80, 500, 350), fill="#194E8C")
    image.save(path)
    assert image_rejection_reason(path) == ""


def test_cookie_and_verification_language_rejected():
    assert text_looks_like_overlay("Manage consent Accept all Reject all")
    assert text_looks_like_overlay("Verify you are human")


def test_tiny_favicon_uses_text_fallback(tmp_path):
    path = tmp_path / "favicon.png"
    Image.new("RGBA", (16, 16), "#00FF00").save(path)
    assert trim_and_fit_logo(path, (200, 80)) is None


def test_logo_is_contained_not_cropped(tmp_path):
    path = tmp_path / "logo.png"
    image = Image.new("RGBA", (500, 100), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((20, 20, 480, 80), fill="#111111")
    image.save(path)
    fitted = trim_and_fit_logo(path, (240, 100))
    assert fitted is not None
    assert fitted.size == (240, 100)
    assert fitted.getchannel("A").getbbox() is not None
