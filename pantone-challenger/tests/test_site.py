import json
from pathlib import Path

from challenger.config import load_sources
from challenger.site import build_site


def test_empty_site_is_real_launch_placeholder_not_demo(tmp_path):
    archive = tmp_path / "archive"
    archive.mkdir()
    site = tmp_path / "site"
    build_site(archive, site, load_sources(Path("config")))
    html = (site / "index.html").read_text()
    assert "FIRST LIVE RESULT IS PENDING" in html
    assert "synthetic" in html.lower()
    assert 'href="./"' in html
