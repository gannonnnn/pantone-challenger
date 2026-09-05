# Challenger Color Index Methodology — Version 1.3

## Research question

Pantone Challenger asks:

> Which color was most unusually prominent across the usable marketing creative in the declared commercial panel for a given day?

It does not claim to measure every advertisement, social post, campaign, or website on the internet.

## Panel and voting unit

The declared panel contains 48 official US-facing marketing pages across 12 sectors, four companies per sector. The source registry is versioned in `config/sources.yml`.

The voting unit is an **independent company**, not a pixel, image, tile, or webpage length. Each company’s daily contribution is normalized to one total vote before cross-company scoring.

## Capture

Each page is rendered in Chromium at a fixed viewport and two configured scroll positions. The system does not log in, bypass access controls, solve CAPTCHAs, or evade blocking.

Full-page frames are retained as private diagnostics. They are not themselves color evidence.

## Eligible marketing-creative regions

V1.3 searches visible page content for likely creative regions such as large `main`, `section`, `article`, `picture`, image, poster, and background-image areas.

The system excludes or rejects regions associated with:

- headers and navigation;
- footers and legal interfaces;
- cookie banners and modal overlays;
- chat widgets and account controls;
- logos, favicons, and small icons;
- regions below the minimum size or confidence thresholds;
- exact duplicate regions.

A company can support a public candidate only when at least one eligible region exists.

## Region-level color extraction

Each eligible region is converted from sRGB into OKLab/OKLCH and reduced to perceptually prominent swatches. Visually similar swatches are merged within the company. Near-black, white, and gray remain measurable but are subject to strict display eligibility and neutral-trend gates.

For every company-to-candidate match, the system retains:

- region identifier and private screenshot path;
- local HEX and OKLab value;
- distance to the cross-company candidate;
- local matched-color share;
- region confidence;
- company name, sector, URL, and page title.

This record is called `CandidateEvidence`.

## Cross-company clustering

Company-normalized swatches are clustered by perceptual distance in OKLab. A company may count at most once for a candidate. Runner-ups must be perceptually distinct from the winner and from one another.

## Persistent house colors

The system reduces colors that are ordinary for a particular company using:

1. optional declared house colors in the source registry; and
2. a learned source-specific baseline from prior accepted V1.3 observations.

Persistent colors are suppressed rather than deleted. They can still matter when their use materially exceeds the company’s own baseline.

## Candidate score

The Challenger Score combines:

- independent company breadth;
- cross-sector breadth;
- source-normalized prevalence;
- creative-region salience;
- source-history momentum;
- evidence-region confidence;
- neutral penalties;
- company and sector concentration penalties.

The method is deterministic for the same inputs and configuration.

## Publication states

### Blocked

The run fails the minimum evidence requirements. Diagnostics are retained, but the result must not be posted.

### Review only

The run has enough evidence to inspect but is still calibrating, has insufficient public-ready coverage, or is a close call. Assets are labeled `INTERNAL CALIBRATION — NOT FOR POSTING`. Review-only days can warm source baselines after merge, but they do not enter recurrence or annual history.

### Ready

The run passes stronger coverage, breadth, region-confidence, distance, concentration, score-margin, and baseline requirements. A human may approve it by merging its review pull request.

## Default quality thresholds

The defaults in `config/settings.yml` include:

- internal review: at least 20 evidence-bearing company pages, seven sectors, and 40% panel coverage;
- public readiness: at least 30 evidence-bearing company pages, nine sectors, and 60% panel coverage;
- winner: at least six companies, four sectors, four traceable regions, sufficient region confidence, and bounded perceptual distance;
- concentration: no company or sector may dominate beyond the configured limits;
- close call: a small score margin remains review-only;
- calibration: seven accepted prior observations are required before a result may become ready.

The configuration file is the authoritative source for exact numeric thresholds.

## Evidence presentation

A logo is attribution only and never color evidence. V1.3 ships with every source set to `text_only`. Public evidence cards show the local matched swatch, company name, authoritative sector, and local share. A brand mark may appear only after a human adds an approved asset and updates the registry.

Raw region screenshots and contact sheets remain private review artifacts.

## Naming

Each candidate has:

- a deterministic color-family label based on its measured OKLCH values; and
- an optional playful creative nickname.

The nickname cannot determine the family. Near-neutral values receive neutral family labels rather than unstable hue names.

## Recurrence and annual summary

Only `ready` results merged into `main` contribute to recurrence and the January Year in Color report. Review-only, blocked, duplicate-date, and reverted results do not count.

Similar colors can belong to the same annual family without requiring identical HEX values. The recurrence method uses conservative complete-link perceptual matching to prevent gradual hue drift.

## Limitations

- The panel is declared, finite, US-facing, and not globally representative.
- Official webpages are only one part of commercial visual culture.
- Websites change structure and may block automated browsers.
- Region detection can still miss creative or admit ambiguous content.
- Early source baselines are weak; this is why V1.3 begins with manual calibration.
- A measured association does not imply that a company coordinated with any other company or endorsed the project.
