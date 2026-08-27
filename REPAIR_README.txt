PANTONE CHALLENGER V1.0.1 — WORKFLOW REPAIR

This repair restores all four GitHub Actions workflows and the corrected test/version files.

Copy the individual files into the matching paths in your cloned repository:

.github/workflows/ci.yml
.github/workflows/daily.yml
.github/workflows/pages.yml
.github/workflows/publish.yml
tests/test_scoring.py
pyproject.toml
CHANGELOG.md

Important: Do not replace the repository's entire .github folder with a partial folder.
This repair package contains the complete workflows folder, so copying the four individual
YAML files into .github/workflows is safest.

Expected workflows after push:
- CI
- Daily Challenger
- Deploy public archive
- Publish approved social package
