# Changelog

## 1.2.0 — Year-to-date recurrence and Year in Color

- Added a visible year-to-date counter to the feed card and first Story.
- Counts perceptually similar winning shades as one color family; exact HEX matches are not required.
- Uses complete-link OKLab matching so a chain of gradually shifting shades cannot silently drift into a different family.
- Added annual family fields to every ready result: winning days, matching dates, current and longest streaks, unique supporting companies, company-page denominator, and sector reach.
- Added recurrence context to captions, review summaries, daily pull requests, publish packages, and the public archive.
- Added `challenger year-end --year YYYY` to generate a January-ready annual report.
- Added a year-in-color social card, a daily winner color grid, annual JSON, and annual Markdown report.
- Added a January 2 GitHub Actions workflow that creates a review pull request for the previous calendar year.
- Added annual pages to the static archive.
- Added recurrence and annual-report regression tests.

## 1.1.0 — Evidence-first social results

- Rebuilt the feed card around a clearly bounded, dominant winner swatch.
- Added named, full-size runner-up swatches with HEX values, source counts, sector counts, and scores.
- Added clear panel denominators throughout the review package: monitored, analyzed, unavailable, supporting, and represented sectors.
- Added first-party brand-mark capture from official page headers, with official site-icon and typographic fallbacks.
- Added supporting-company logo cards with company names, sectors, and source-level visual salience.
- Added runner-up names, source sectors, source salience, source-logo provenance, and a structured `review_summary` to the evidence archive.
- Added a visual review summary and an image-rich pull-request body.
- Added a downloadable social-package artifact alongside private raw-capture evidence.
- Added company/source coverage, supporting marks, and runner-up swatches to the public archive.
- Added explicit no-endorsement language for monitored company marks.
- Updated the daily artifact uploader and added rendering/logo-normalization regression tests.

## 1.0.1 — Launch workflow hotfix

- Corrected a scoring test fixture that unintentionally triggered the unchanged-page penalty.
- Gated GitHub Pages deployment behind the `ENABLE_PAGES=true` repository variable.
- Prevented a private repository from showing a failed Pages build before Pages is enabled.

## 1.0.0 — Production launch build

- Replaced synthetic input with browser-rendered official marketing pages.
- Added 48-source, 12-sector declared panel.
- Added exact and conservative near-duplicate checks.
- Added perceptual OKLab/OKLCH color extraction.
- Added one-normalized-vote-per-source behavior.
- Added source-specific brand-color baseline suppression.
- Added unchanged-page suppression.
- Added transparent Challenger Score and quality gate.
- Added deterministic cultural color naming.
- Added feed and four Story renderers.
- Added evidence archive and static public site.
- Added nightly review-pull-request workflow.
- Added GitHub Pages workflow.
- Added approval-gated Instagram and Bluesky publishers.
- Added social publish locks and receipts.
- Added Eastern marketing-day resolution with regression tests.
- Added source/rights policy and non-affiliation notice.
