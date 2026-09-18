# Changelog

## 1.6.1 — repair temporal evidence capture

- Preserve explicit publication dates within a selected item, or on its linked detail page, with bounded detail requests and private HTML evidence.
- Admit an opted-in, time-stamped ranked chart as attention evidence only when image, item link, and rank associations are present. A chart date is never a release date or proof of growth.
- Include Apple Music Charts in each daily discovery sample without increasing the 18 discovery slots or 58 total sources.
- Separate exhibition start/end dates, apply the configured 45-day opening window to newly exhibited work, and reject ended events.
- Skip partial and out-of-window MusicBrainz release dates before requesting cover images.
- Show attempted, captured, admitted, and current source counts for each stage, with named missing-date sources and diagnostic files in both artifacts.
- Add offline browser capture regressions required by CI and daily collection. Retain the existing quality gates and start a new compatible baseline for the changed date-admission rules.

## 1.6.0 — comparable evidence and optional AI review

- Matched the update to the user's uploaded v1.5.2 repository, preserving its additional project files and source registry.
- Included the missing v1.5.3 runtime repair: one shared browser, source deadlines, progress reporting, and bounded GitHub workflows.
- Compared observed benchmark groups on both sides of each date pair; coverage changes alone cannot create growth.
- Admitted dated, substantive evidence before ranking; excluded blocked and incompatible baseline records.
- Kept unverified creators grouped at their publisher and retained verified marketplace seller identities where available.
- Added atomic rebuilds, same-day local resume, captured-image retention, and archive verification before publication.
- Corrected support counts and story layouts, and added a linked Color Trail.
- Added manual AI image annotations with a dry run, caching, bounded requests, and human-label evaluation. Annotations do not affect rankings.
- Changed live `auto` to the actual observation date in the configured timezone; rebuilding a past date from today's webpages is rejected.


## 1.5.2 hotfix — CI and tie eligibility

- Recomputes neutral status from each candidate HEX before tie evaluation, preventing grays from being treated as eligible co-Challengers.
- Aligns the main settings and fallback methodology version with V1.5.2.
- Restores one pull-request CI check instead of duplicate push and pull-request checks on repair branches.
- Limits lint gating to code-breaking Python errors while retaining the full test and release-validation suite.
- Updates Daily Challenger artifact actions to Node 24-compatible major versions.

## 1.5.1 — Color Truth and Pixel Provenance

- Corrects OKLCH family boundaries so red, yellow, cyan, and blue are no longer mislabeled.
- Clusters source pixels in OKLab rather than raw RGB.
- Uses an actual source pixel as every local and public display HEX.
- Adds complete-linkage cross-source clustering to prevent color-family drift.
- Suppresses border-connected neutral page infrastructure without deleting it from regime analysis.
- Adds connected-area and spatial-coverage gates for scattered UI accents.
- Excludes transparent padding instead of compositing a fake beige background.
- Produces a private color-proof sheet that highlights the exact matching pixels.
- Reopens all evidence at runtime and hard-stops the run if any extracted or candidate HEX is absent from the decoded source pixels.
- Resets the color baseline through a compatibility key so earlier synthetic centroids cannot influence trend scoring.
- Waits for lazy imagery to decode and correctly measures image elements themselves.

## 1.5.0 — Cultural Signal Matrix

- Expands measurement beyond company marketing into art, fashion, marketplaces, advertising, design, interiors, entertainment, creator culture, audience intent, materials, and the public visual field.
- Classifies every source by domain, industry sector, signal stage, scale class, panel type, event type, geography, platform, and rights mode.
- Separates stable benchmark sources from rotating discovery sources.
- Preserves creative-region extraction, overlay rejection, equal source voting, house-color history, duplicate campaign reduction, neutral gating, and evidence traceability.
- Adds Undercurrent, Challenger, Mainstream Leader, and Raw Usage Leader classifications.
- Adds ties, palette pairings, and palette-regime metrics.
- Adds official API adapters for open-access art, music/film artwork, marketplaces, and creator launches; token-dependent connectors are off by default.
- Adds an approved community-signal inbox and GitHub issue form.
- Adds a static historical website and JSON feed suitable for GitHub Pages.
- Adds annual regime and color-family summaries.
- Adds safer image and logo handling: no favicon fallback, contain-only fitting, max 2× enlargement, transparent-padding trim, exact swatch validation, text fallback, and rights-aware public output.

## 1.5.2 — Temporal and Semantic Integrity

- Rejects future-dated feed and API evidence for the requested cultural date.
- Moves undated historical art, catalogs, and static benchmark material to context or baseline-only roles.
- Tracks first-seen, last-seen, and last-changed evidence fingerprints.
- Requires meaningful connected color area rather than scattered incidental pixels.
- Tightens muted and low-chroma candidate coherence.
- Evaluates ties only after candidate eligibility and neutral filtering.
- Suppresses emergence claims until seven prior valid baseline days exist.
- Reports source counts by domain, signal stage, scale class, panel, and sector.
- Quarantines public assets whenever postflight integrity checks block a result.
