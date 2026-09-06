from __future__ import annotations

from pathlib import Path

from PIL import Image

from challenger.color_truth import audit_color_truth, require_color_truth
from tests.helpers import candidate, observation


def test_runtime_audit_reopens_images_and_verifies_exact_pixels(tmp_path):
    obs = observation(tmp_path, "source-a", "#E9342E")
    c = candidate("#E9342E", source_count=1, domains=1, stages=1)
    evidence_path = tmp_path / "candidate-evidence.png"
    Image.new("RGB", (80, 60), "#E9342E").save(evidence_path)
    c.evidence[0].region_path = str(evidence_path)
    report = audit_color_truth([obs], [c])
    assert report["passed"] is True
    assert report["extracted_swatches_checked"] == 1
    assert report["candidate_evidence_records_checked"] >= 1


def test_runtime_audit_rejects_a_claimed_hex_absent_from_image(tmp_path):
    obs = observation(tmp_path, "source-a", "#E9342E")
    obs.swatches[0].hex = "#115BB9"
    obs.swatches[0].observed_pixel = True
    report = audit_color_truth([obs], [])
    assert report["passed"] is False
    assert any(error["scope"] == "swatch_pixel" for error in report["errors"])


def test_runtime_audit_is_a_hard_invariant(tmp_path):
    obs = observation(tmp_path, "source-a", "#E9342E")
    obs.swatches[0].hex = "#115BB9"
    try:
        require_color_truth([obs], [])
    except RuntimeError as exc:
        assert "No result may be rendered or published" in str(exc)
    else:
        raise AssertionError("Expected a color-truth failure")
