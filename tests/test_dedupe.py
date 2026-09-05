import hashlib
from pathlib import Path

from PIL import Image

from challenger.dedupe import deduplicate_records
from challenger.models import CaptureRecord, EvidenceRegion


def record(source_id: str, path: Path) -> CaptureRecord:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return CaptureRecord(
        source_id=source_id,
        source_name=source_id,
        sector="retail",
        url=f"https://example.com/{source_id}",
        success=True,
        regions=[
            EvidenceRegion(
                source_id=source_id,
                frame_id="f01",
                region_id=f"{source_id}-r01",
                selector_hint="main",
                region_type="hero",
                path=str(path),
                sha256=digest,
                bbox=(0, 0, 200, 120),
                viewport_area_ratio=0.10,
                image_area_ratio=1.0,
                text_density=0.0,
                confidence=0.9,
            )
        ],
    )


def test_exact_duplicate_casts_only_one_vote(tmp_path):
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    Image.new("RGB", (200, 120), "#A14D55").save(first)
    second.write_bytes(first.read_bytes())
    records = [record("a", first), record("b", second)]
    deduplicate_records(records)
    assert records[0].success
    assert not records[1].success
    assert "Exact duplicate" in records[1].error
