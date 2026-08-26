# Challenger Color Index Methodology — Version 1.0

## Research question

Pantone Challenger asks:

> Which color was most unusually prominent across the usable official marketing pages in the declared panel for a given commercial day?

It does not claim to identify the most common color across all advertising, all social media, or the entire internet.

## Sampling unit

The voting unit is an **independent source**, not a pixel and not an image.

Each configured brand or commercial organization receives one normalized daily contribution regardless of:

- how many images are present;
- how many repeated tiles appear;
- how long the page is;
- how many products it lists.

This prevents a visually dense retailer from outweighing a simpler campaign page merely because it renders more pixels.

## Panel

Version 1.0 uses 48 official marketing pages across 12 sectors, with four sources in each sector. The panel is declared in `config/sources.yml`.

The panel is intentionally broad but not globally representative. It is currently US-facing and English-language. Future geographic panels should be published as separate indices rather than silently mixed into the baseline.

## Capture

Each source is rendered in Chromium with:

- a fixed 1440 × 1200 CSS-pixel viewport;
- US English locale;
- America/New_York timezone;
- light color scheme;
- reduced motion;
- two fixed scroll positions;
- a limited request rate.

Video and websocket resources are blocked to improve reproducibility. Images, CSS, and fonts remain available.

The system attempts to dismiss a small list of ordinary consent buttons. It does not bypass CAPTCHAs, authentication, paywalls, or access controls.

Pages displaying likely block or challenge signatures are marked unusable.

## Commercial date

GitHub cron schedules use UTC. The index resolves each run into `America/New_York` and applies a 4 a.m. local rollover. This prevents a near-midnight scheduled run from being archived under the wrong Eastern calendar date during daylight-saving transitions.

The production capture is scheduled for 03:30 UTC, corresponding to late evening Eastern in both standard and daylight time.

## Duplicate control

The system removes:

1. exact screenshot duplicates using SHA-256;
2. only highly conservative near duplicates requiring:
   - near-identical difference hashes;
   - nearly identical mean RGB;
   - similar file sizes.

Near-duplicate thresholds intentionally favor false negatives over suppressing independent pages.

## Color extraction

Each captured frame is:

1. converted to RGB;
2. cropped slightly to reduce browser-edge and persistent navigation influence;
3. resized for stable computation;
4. converted from sRGB into OKLab;
5. center-weighted;
6. weighted partly by chroma;
7. stripped only of nearly empty pure-white and pure-black extremes;
8. clustered with deterministic weighted k-means;
9. merged across frames by perceptual distance.

Ordinary whites, grays, blacks, and beiges remain eligible. They are not secretly removed; they face a published neutral penalty later.

Each source’s retained swatches are normalized to sum to one.

## Source-specific baseline suppression

A brand’s ordinary identity color is not automatically a cultural trend.

For each source and current swatch, the system looks for perceptually similar swatches in that same source’s trailing history. Persistent colors are downweighted using:

```text
rarity = current_share / (current_share + 2 × baseline_share)

rarity_factor =
    (1 − suppression_strength)
    + suppression_strength × rarity
```

The adjusted share is blended with the original share during a seven-day warmup. Full suppression begins only when enough source history exists.

If a source's current screenshot hashes exactly match its most recent usable day,
all of its color contributions receive an additional unchanged-page factor. Version
1.0 uses `0.35`. A page that has not visibly changed can still provide context, but
it cannot carry the same daily-trend weight as new creative.

This means:

- Spotify green does not win merely because Spotify remains green.
- Target red does not win merely because Target remains red.
- A red that suddenly spreads across unrelated brands and industries can still win.

## Cross-source clustering

Current source swatches are merged into global color candidates using Euclidean distance in OKLab.

A source can contribute only its strongest matching swatch to a given global candidate.

Candidates supported by fewer than two sources are discarded before ranking.

## Challenger Score

The score begins with five positive components:

```text
30 points — independent source breadth
22 points — commercial sector breadth
20 points — momentum versus trailing prevalence
18 points — mean adjusted visual salience
10 points — prevalence within the usable panel
```

The system then subtracts:

```text
up to 23 points — neutral/extreme-lightness penalty
up to 12 points — single-sector concentration penalty
```

### Independent source breadth

Full credit is reached at 12 independent sources.

### Sector breadth

Full credit is reached when the candidate appears across approximately 65% of the usable sectors.

### Momentum

During the first seven baseline days, momentum is held at a neutral value.

After warmup:

```text
ratio = (current_prevalence + 0.02)
        / (baseline_prevalence + 0.02)

momentum = clamp(
    0.40 + 0.30 × log2(ratio),
    0,
    1
)
```

### Visual salience

Adjusted per-source swatch share is normalized against a 30% reference level.

### Neutral penalty

Colors below approximately 0.065 OKLCH chroma receive a graduated penalty. Near-white or near-black low-chroma colors receive an additional penalty.

Neutral colors can still win if their breadth, salience, and momentum are strong enough.

### Concentration penalty

If more than half of a candidate’s sources come from one sector, the score is reduced. This rewards genuinely cross-commercial spread.

## Quality gate

A result is blocked unless all of the following are true:

- at least 20 sources are usable;
- at least 8 sectors are usable;
- at least 3 supported color candidates exist;
- the leader appears in at least 5 independent sources;
- the leader crosses at least 3 sectors.

A blocked day remains available for technical diagnosis but produces no social package and no public result.

## Naming

The color name is deterministic, using:

- OKLCH hue family;
- lightness;
- chroma;
- the date;
- supporting sectors;
- a fixed vocabulary of contemporary commercial objects and qualifiers.

The naming system does not choose the color. Editing a name for safety or clarity does not alter the result, but Version 1.0 does not include an automated override path.

## Human review

Humans may reject publication because:

- the capture sample is misleading;
- a block page survived detection;
- rights metadata or attribution is wrong;
- the output is broken;
- the written claim exceeds the methodology;
- a safety issue exists.

Humans may not substitute another candidate because the winner is unattractive, unfashionable, boring, or inconvenient.

## Versioning

Any change to:

- source panel composition;
- sampling method;
- color extraction;
- baseline suppression;
- scoring weights;
- quality thresholds;
- naming vocabulary;

must be committed and documented. Material scoring changes increment the methodology version and apply prospectively.

Historical results are never silently recomputed under a new methodology.

## Known limitations

Version 1.0:

- measures brand-owned official pages rather than paid-ad impression volume;
- is US-facing and English-language;
- observes a late-evening snapshot, not every creative shown throughout the day;
- can lose sources to bot protection or geographic variation;
- may undercount video-first campaigns because video requests are blocked;
- uses page prominence as a proxy, not audience exposure;
- treats sectors as configured categories rather than learned cultural categories;
- cannot infer why a color was chosen;
- does not establish causation between simultaneous brand color choices.

These limitations are part of the public interpretation, not hidden implementation details.
