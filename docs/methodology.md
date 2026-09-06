# Methodology: the Open Cultural Color Index

Pantone Challenger asks a different question from an annual expert color selection:

> Which colors are beginning, spreading, converging, and becoming ordinary across culture now?

## A two-dimensional signal matrix

Every source is classified by:

1. **Cultural domain** — art, fashion, marketplace, advertising, design and interiors, entertainment, technology, independent creation, audience intent, materials, public visual culture, or lifestyle.
2. **Signal stage** — creation, distribution, or attention.

It also records source scale, panel type, event type, geography, rights mode, platform, and authoritative industry sector.

## Stable and rotating panels

The **benchmark panel** is sampled consistently so day-over-day and source-level comparisons remain meaningful.

The **discovery panel** rotates across small, independent, institutional, marketplace, and experimental sources. It exists to find signals the benchmark does not yet know about.

Large sources provide confidence. Small sources provide discovery. Neither is allowed to become the whole index.

## What counts as evidence

For a webpage, a color must come from an eligible creative region such as a campaign image, product collection, exhibition, poster, editorial artwork, or large visual section. Navigation, logos, favicons, cookie notices, verification pages, modal offers, blank space, and loading placeholders are rejected.

For official APIs and feeds, the image is tied to a specific object, listing, release, or publication event.

Every source displayed behind a candidate retains a local swatch, creative-region identifier, perceptual distance, local share, confidence, URL, rights mode, and registry classification.

## Image integrity

- Transparent padding is trimmed before analysis.
- Tiny favicons are not public brand marks.
- Logos never cast color votes.
- Public logos require a manually approved asset; otherwise the company or source name is rendered as text.
- Logos use contain fitting, are never cropped, and are not enlarged by more than 2×.
- Cross-source exact and near-duplicate imagery is reduced so a syndicated campaign does not become many independent votes.
- Light swatches receive visible boundaries.
- Automated tests verify that winner and runner-up swatch pixels match the declared HEX values.
- Every daily run independently reopens the private evidence and verifies that all extracted and candidate HEX values occur in decoded source pixels. A mismatch is a hard software-integrity failure.
- Cross-source display colors are observed medoids, not synthetic average centroids.

## Popularity versus emergence

The system separately computes:

- **Raw usage leader** — what is broadly visible today.
- **Mainstream leader** — what is visible across benchmark and large sources.
- **Undercurrent** — what is strongest among independent, grassroots, or discovery sources.
- **Challenger** — what is emerging across unrelated domains and signal stages.

The public Challenger is selected by reproducible statistics, not an LLM. AI may help name and explain a measured result after selection.

## Historical comparison

Each source is compared with itself. A permanent brand blue is not novel merely because it appeared again. The engine measures new adoption, rising local use, panel lift, acceleration, cross-domain spread, cross-stage convergence, source-scale diversity, and evidence quality.

Candidate states are New, Rising, Spreading, Surging, Stable, Identity, Cooling, or Calibration.

## Ties and palette pairings

A tie is allowed when qualified candidates have near-equal scores and overlapping uncertainty. A palette pairing is different: it means two colors repeatedly appear together inside the same creative work.

A tied color receives one appearance day and a fractional leaderboard day-share for annual aggregation.

## Palette regimes

A single HEX cannot describe a visual era. Daily and monthly reports also track neutral share, chroma, lightness, warm/cool balance, contrast, palette size, monochromatic share, muted/electric balance, and recurring color pairs.

## No forced winner

Valid outcomes are Ready, Review Only, Baseline Only, and Blocked. A day with no trustworthy emerging color can still improve the baseline without creating a social post.
