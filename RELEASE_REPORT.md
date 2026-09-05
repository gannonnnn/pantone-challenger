# Pantone Challenger 1.3.0 Release Report

## Purpose

V1.3 repairs the evidence model exposed by the first live-result reviews. Earlier builds could mistake full-page visual infrastructure for campaign color and could display tiny or misleading favicons beside a winner. The new version requires every supporting company to trace to an eligible marketing-creative region and a local color swatch perceptually close to the candidate.

## Included

- Region-level capture and color extraction.
- Traceable per-company evidence records.
- One normalized vote per company.
- Registry-authoritative company names and sectors.
- Text-only public attribution for all 48 sources until individual brand marks are manually approved.
- No public favicon fallback.
- Three publication states: `ready`, `review_only`, and `blocked`.
- Seven-run internal calibration period.
- Manual-only Daily Challenger workflow during calibration.
- Stronger coverage, evidence, distinctness, and concentration gates.
- Private evidence contact sheets and exact social-swatch rendering.
- Recurrence and annual-summary protection so only approved `ready` results count.

## Validation completed in the build environment

- 36 automated tests passed.
- Python source and tests compiled successfully.
- Configuration and GitHub workflow YAML parsed successfully.
- The declared panel contains 48 sources across 12 sectors, four per sector.
- All 48 sources default to text-only attribution.
- A private synthetic integration run exercised the complete analysis and rendering path and correctly produced an internal calibration package.

The synthetic integration run was only a controlled engineering test. It is not included in this release and must not be described as a live commercial-color finding.

## Validation still required in the owner’s GitHub repository

- CI must pass after the upgrade pull request is pushed.
- Seven manual full-panel shadow runs must be reviewed.
- Live website structure, capture quality, and source availability must be assessed from private evidence artifacts.
- Daily scheduling must remain disabled until the owner explicitly approves the V1.3 behavior.
