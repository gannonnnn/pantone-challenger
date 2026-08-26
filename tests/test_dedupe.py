import hashlib
from pathlib import Path

from PIL import Image

from challenger.dedupe import deduplicate_records
from challenger.models import CaptureFrame, CaptureRecord


def record(source_id: str, path: Path) -> CaptureRecord:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return CaptureRecord(
        source_id=source_id,
        source_name=source_id,
        sector="retail",
        url=f"https://example.com/{source_id}",
        success=True,
        frames=[CaptureFrame(path=str(path), scroll_y=0, sha256=digest)],
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
