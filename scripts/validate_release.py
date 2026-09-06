from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from challenger import __version__  # noqa: E402
from challenger.config import load_settings, load_sources  # noqa: E402


def main() -> int:
    errors = []
    settings = load_settings()
    version, sources = load_sources()
    if __version__ != "1.5.1":
        errors.append(f"Unexpected package version: {__version__}")
    if settings.get("methodology_version") != "1.5.1":
        errors.append("Methodology version is not 1.5.1")
    enabled = [s for s in sources if s.enabled]
    if len(enabled) < 50:
        errors.append("The enabled cultural panel has fewer than 50 declared sources")
    if len({s.domain.value for s in enabled}) < 10:
        errors.append("The panel spans fewer than 10 cultural domains")
    if {s.signal_stage.value for s in enabled} != {"creation", "distribution", "attention"}:
        errors.append("Creation, distribution, and attention are not all represented")
    if {s.panel_type.value for s in enabled} != {"benchmark", "discovery"}:
        errors.append("Benchmark and discovery panels are not both represented")
    required_workflows = {"ci.yml", "daily.yml", "pages.yml", "publish.yml", "year-end.yml"}
    found = {p.name for p in (ROOT / ".github/workflows").glob("*.yml")}
    missing = required_workflows - found
    if missing:
        errors.append(f"Missing workflows: {sorted(missing)}")
    forbidden_names = []
    for path in ROOT.rglob("*"):
        if any(part in {".git", ".venv", "__pycache__", ".pytest_cache", "tests"} for part in path.parts):
            continue
        if path.name.lower() in {"demo-output", "preview", "previews", "synthetic-results.json"}:
            forbidden_names.append(str(path.relative_to(ROOT)))
    if forbidden_names:
        errors.append(f"Forbidden production fixture paths: {forbidden_names}")
    secret_patterns = [
        re.compile(r"(?i)(access[_-]?token|api[_-]?key|app[_-]?password)\s*[:=]\s*['\"]?[A-Za-z0-9_-]{24,}"),
        re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    ]
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".zip"}:
            continue
        if path.name == ".env.example":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if any(pattern.search(text) for pattern in secret_patterns):
            errors.append(f"Potential secret in {path.relative_to(ROOT)}")
    source_yaml = yaml.safe_load((ROOT / "config/sources.yml").read_text(encoding="utf-8"))
    for raw in source_yaml.get("sources", []):
        if "sector" not in raw:
            errors.append(f"Source {raw.get('id')} lacks authoritative sector")
        if raw.get("brand_mark_status") == "approved":
            asset = ROOT / raw.get("brand_mark_path", "")
            if not asset.exists():
                errors.append(f"Approved brand mark missing for {raw.get('id')}")
    report = {
        "version": __version__,
        "registry_version": version,
        "enabled_sources": len(enabled),
        "domains": sorted({s.domain.value for s in enabled}),
        "stages": sorted({s.signal_stage.value for s in enabled}),
        "benchmark_sources": sum(s.panel_type.value == "benchmark" for s in enabled),
        "discovery_sources": sum(s.panel_type.value == "discovery" for s in enabled),
        "errors": errors,
    }
    (ROOT / "release-validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
