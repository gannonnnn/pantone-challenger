# Pantone Challenger v1.6.0 — validation record

Revised 2026-09-17 against the uploaded `pantone-challenger-current.zip`, which identifies itself as v1.5.2. The installer includes both the missing v1.5.3 runtime repair and the previously tested v1.6.0 improvements. This is an implementation package, not a deployed release or a claim about live color trends.

## Automated checks

| Check | Result |
| --- | --- |
| Uploaded v1.5.2 suite before changes | 58 passed |
| Updated complete suite | 99 passed |
| Critical Python lint: E9, F63, F7, F82 | Passed |
| Git patch whitespace check | Passed |
| Temporal/semantic validation script | Passed |
| Runtime validation script | Passed |
| Source/release validation script | Passed |

Runtime: Linux, Python 3.12.14. Two existing Pillow deprecation warnings remain in legacy temporal image checks; they did not affect the result. The application depends on compatible version ranges rather than a fully locked dependency file. GitHub CI installs and verifies the environment again.

The registry validation found 67 enabled sources across 12 domains and three stages. The configured daily selection contains 40 benchmark and 18 rotating discovery sources, totaling 58. These are configuration counts, not successful live captures.

## Behaviors exercised

- Extra source coverage alone does not create measured growth.
- Changing item URLs does not create independent creator votes.
- Missing source observations remain unknown; genuinely increased prevalence within an adequately observed benchmark cohort can qualify.
- Rotating discovery sources cannot enlarge the benchmark comparison denominator.
- Historical and future-dated evidence is excluded before candidate ranking.
- Undated benchmark observations can warm the baseline without making a current-emergence claim.
- Blocked and incompatible archives cannot advance the new baseline.
- Frozen candidates agree with admitted evidence, source-group counts, and observed representative HEX values.
- A failed rebuild leaves the previous archived result intact.
- Resume reuses intact successful captures and retries failed sources.
- An intentionally uncooperative API worker is terminated within its hard deadline.
- Captions distinguish winner support from total coverage.
- A modified archive fails verification; the site builder refuses a record changed to ready.
- The Color Trail excludes future and blocked observations.
- AI dry runs issue zero requests. Mocked structured responses, cache reuse, invalid output, failure handling, time limits, and held-out evaluation were exercised.
- The installer creates and stages a new branch while preserving the original commit; it refuses newer source, uncommitted work, and a damaged package.

## Visual checks

Rendered controlled test evidence through the actual production templates and inspected the feed, evidence cards, explanation card, category chart, and contact sheet. Source names now wrap within the evidence cards. Category groups fit within the story canvas, and the explanation card reports comparable history and prevalence change. These internal layout fixtures are not live observations and are not included as public results.

## Installation verification

The packaged patch is checked against a fresh checkout made from the uploaded v1.5.2 ZIP. Its installed file tree must match the complete updated source byte for byte; the original branch must remain at the baseline commit. The package includes a patch checksum and pre-change file hashes so the installer can stop before editing a different source version. The source registry and additional historical reports, policies, and site files from the uploaded repository are retained.

Upload SHA-256: `e7778869f018f392532bd456240b4b33f7cf0af9b940d6107d04c157bb0b629f`.

## Not established by this validation

- No code has been pushed to the user's GitHub repository or deployed.
- A full live collection was not completed here. Live page availability, selectors, authentication, and anti-bot behavior still need the first manual GitHub run. The earlier validation environment could not complete Chromium's download; no live browser validation is claimed for this adaptation.
- No paid OpenAI API request was made. The API integration was tested with mocked Responses payloads; annotation accuracy needs a human-labelled set of real project images.
- The package does not migrate old snapshots into the new baseline. At least seven valid collection dates and sufficient comparable source history are needed; seven calendar days do not guarantee a public Challenger.
- Website generation was checked in code and tests. The live Pages deployment and browser presentation on the user's domain were not tested.
- The installer refuses changed files rather than attempting an unreviewed merge into a newer live repository. A current source export is required if that check fails.

## Reproduce the checks

From a Python 3.11+ environment in the updated source folder:

```bash
python -m pip install -e ".[dev]"
pytest -o addopts='' -q
ruff check challenger tests scripts --select E9,F63,F7,F82
python scripts/validate_temporal_integrity.py
python scripts/validate_runtime.py
python scripts/validate_release.py
```

See `IMPLEMENTATION.md` in the update package, or `docs/IMPLEMENT_V1.6.md` in the source tree, for the installation and live verification steps.
