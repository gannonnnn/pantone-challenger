# Changelog

## 1.3.0 — Evidence integrity and calibration repair

- Replaced full-page palette support with traceable marketing-creative regions.
- Added `EvidenceRegion` and `CandidateEvidence` records so every displayed company match retains a source region, local HEX, perceptual distance, share, and confidence.
- Prevented headers, navigation, footers, cookie overlays, logos, icons, and full-page backgrounds from casting public color votes.
- Normalized each company to one vote per cross-source candidate.
- Added authoritative source-registry validation for company names and sectors.
- Set all 48 public source cards to text-only attribution by default; runtime favicon fallback is prohibited.
- Redesigned evidence cards around the company’s measured local swatch rather than its logo.
- Added `ready`, `review_only`, and `blocked` publication states.
- Marked the first seven accepted runs as internal calibration and excluded them from recurrence and year-end history.
- Made Daily Challenger manual-only during the V1.3 shadow-run period.
- Added stronger panel coverage, source breadth, sector breadth, evidence confidence, perceptual distance, concentration, and close-call gates.
- Added exact winner and runner-up swatch rendering checks, color-family validation, and text-fallback behavior.
- Added a private evidence contact sheet for human review.
- Added regression tests for page-background winners, favicon-as-evidence, sector mismatches, neutral misnaming, placeholder contamination, and incorrect rendered HEX values.
- Updated GitHub artifact workflows to `actions/upload-artifact@v7`.

## 1.2.1 — Chromatic-result and logo normalization hotfix

- Prevented cold-start page infrastructure colors such as near-black, white, and gray from becoming the public winner or runner-ups.
- Added neutral-aware naming, swatch borders, logo normalization, and singular recurrence copy.

## 1.2.0 — Year-to-date recurrence and Year in Color

- Added perceptual color-family recurrence, streaks, company and sector reach, annual summary JSON, social graphics, and the January Year-End Challenger workflow.

## 1.1.0 — Evidence-first social results

- Added visible winner and runner-up swatches, panel denominators, supporting-company cards, image-rich review pull requests, and social-package artifacts.

## 1.0.1 — Launch workflow hotfix

- Corrected the initial scoring fixture and gated Pages behind `ENABLE_PAGES=true`.

## 1.0.0 — Production launch build

- Added the 48-source panel, browser capture, perceptual clustering, source-normalized scoring, social rendering, GitHub review workflows, static archive, and optional publishers.
