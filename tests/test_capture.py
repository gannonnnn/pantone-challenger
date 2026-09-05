import hashlib

from PIL import Image, ImageDraw

from challenger.config import Settings
from challenger.evidence import observation_from_capture
from challenger.models import CaptureRecord, EvidenceRegion
from challenger.pipeline import observations_from_captures


def test_creative_region_becomes_traceable_observation(tmp_path):
    region_path = tmp_path / "region.png"
    image = Image.new("RGB", (700, 420), "#A5C84A")
    draw = ImageDraw.Draw(image)
    draw.rectangle((480, 0, 700, 420), fill="#477FA2")
    image.save(region_path)
    digest = hashlib.sha256(region_path.read_bytes()).hexdigest()

    record = CaptureRecord(
        source_id="example",
        source_name="Example",
        sector="technology",
        url="https://example.com",
        final_url="https://example.com",
        title="Example campaign",
        captured_at="2026-08-30T12:00:00-04:00",
        success=True,
        regions=[
            EvidenceRegion(
                source_id="example",
                frame_id="f01",
                region_id="f01-r01",
                selector_hint="main.hero",
                region_type="hero",
                path=str(region_path),
                sha256=digest,
                bbox=(0, 0, 700, 420),
                viewport_area_ratio=0.20,
                image_area_ratio=0.95,
                text_density=0.1,
                confidence=0.90,
            )
        ],
    )

    observation = observation_from_capture(record, Settings())

    assert observation is not None
    assert observation.source_id == "example"
    assert len(observation.regions) == 1
    assert observation.regions[0].screenshot_path == str(region_path)
    assert observation.swatches
    assert max(item.oklch[1] for item in observation.swatches) > 0.10


def test_full_page_without_creative_region_is_not_color_evidence():
    record = CaptureRecord(
        source_id="example",
        source_name="Example",
        sector="technology",
        url="https://example.com",
        success=True,
        regions=[],
    )
    assert observation_from_capture(record, Settings()) is None


def test_failed_or_deduplicated_record_cannot_cast_a_vote(tmp_path):
    region_path = tmp_path / "region.png"
    Image.new("RGB", (700, 420), "#A5C84A").save(region_path)
    digest = hashlib.sha256(region_path.read_bytes()).hexdigest()
    record = CaptureRecord(
        source_id="duplicate",
        source_name="Duplicate",
        sector="technology",
        url="https://example.com/duplicate",
        success=False,
        error="Exact duplicate of another source",
        regions=[
            EvidenceRegion(
                source_id="duplicate",
                frame_id="f01",
                region_id="duplicate-f01-r01",
                selector_hint="main.hero",
                region_type="hero",
                path=str(region_path),
                sha256=digest,
                bbox=(0, 0, 700, 420),
                viewport_area_ratio=0.20,
                image_area_ratio=0.95,
                text_density=0.1,
                confidence=0.90,
            )
        ],
    )

    assert observations_from_captures([record], Settings()) == []
