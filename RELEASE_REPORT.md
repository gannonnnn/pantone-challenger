# Pantone Challenger 1.2.0 Release Report

This cumulative release keeps the evidence-first V1.1 result design and adds a durable year-to-date recurrence system plus a January-ready Year in Color report.

## Included

- Large winner-color treatment, visible runner-up swatches, first-party company marks, and explicit monitored/analyzed/supporting counts from V1.1.
- A year-to-date counter on the feed card, first Story, caption, pull-request review, result JSON, and public archive.
- Perceptual color-family matching in OKLab, so close shades can count together without requiring identical HEX values or identical creative names.
- Complete-link matching, which requires every shade in a family to remain within the fixed threshold of every other shade and prevents gradual color drift.
- Daily recurrence fields for winning days, matching dates, current and longest streaks, unique supporting companies, panel denominator, supporting company-days, average analyzed pages, and cross-sector reach.
- `challenger year-end --year YYYY` for a January-ready annual report built only from approved daily results.
- Annual JSON and Markdown reports, a Year in Color summary card, and a grid of every approved daily winner.
- A scheduled/manual **Year-End Challenger** GitHub Actions workflow that opens a review pull request rather than publishing automatically.
- Annual pages in the static archive.
- Updated launch and methodology documentation.

## Validation

- 19 automated tests passed.
- Python application and tests compiled successfully.
- All 48 declared sources remain balanced across 12 sectors, four sources per sector.
- Workflow and configuration YAML parsed successfully.
- Daily recurrence, year reset, stable family naming, complete-link grouping, annual aggregation, and annual asset generation have regression coverage.
- The daily recurrence and annual summary graphics were visually inspected at 1080×1350 and 1080×1920.

The included previews use illustrative placeholder results solely to show the new layout. They are not represented as live measured findings. A daily counter uses only approved historical results on `main`, plus the current measured result being reviewed.
