from pathlib import Path


def test_daily_workflow_is_manual_only_during_v13_calibration():
    workflow = Path(".github/workflows/daily.yml").read_text()
    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "actions/upload-artifact@v7" in workflow
    assert "INTERNAL CALIBRATION — DO NOT POST" in workflow
    assert 'branch="calibration/$day"' in workflow


def test_social_publisher_is_manual_only_during_v13_calibration():
    workflow = Path(".github/workflows/publish.yml").read_text()
    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow


def test_repository_contains_no_publishable_preview_fixture():
    forbidden = [
        path
        for path in Path(".").rglob("*")
        if path.is_file()
        and any(part in {"preview", "previews", "demo-output"} for part in path.parts)
    ]
    assert forbidden == []
