from pathlib import Path


def test_no_demo_or_preview_assets_in_production_tree():
    root = Path(__file__).resolve().parents[1]
    forbidden = []
    for path in root.rglob("*"):
        if any(part in {".git", ".venv", "__pycache__", "tests"} for part in path.parts):
            continue
        name = path.name.lower()
        if "demo-output" in name or "preview-data" in name or name == "synthetic-results.json":
            forbidden.append(path)
    assert not forbidden
