# Pantone Challenger

**Pantone Challenger watches a declared panel of official commercial marketing pages and identifies the color that was most unusually prominent yesterday.**

It is a small computational art project with a real production loop:

1. Browser-render 48 official marketing sites across 12 commercial sectors.
2. Extract perceptually prominent colors from two consistent page viewports.
3. Give each brand one normalized vote.
4. Suppress colors that are ordinary for that particular brand.
5. Cluster similar shades in OKLab.
6. Reward independent cross-sector spread, momentum, and visual salience.
7. Block the day if the source sample is too weak.
8. Match the winner against prior approved days to maintain a year-to-date color-family counter.
9. Render one feed post and four Story cards with explicit swatches, company marks, panel coverage, and recurrence context.
10. Open a GitHub pull request for human review.
11. Merge to approve the public archive and, optionally, social publishing.
12. Generate a Year in Color package in January from approved daily results.

The machine chooses the color. A human may stop a broken or misleading result, but may not replace the winner merely because another shade would look prettier.

> **Pantone Challenger is independent and is not affiliated with, sponsored by, or endorsed by Pantone LLC.** The project does not use Pantone color codes, proprietary swatches, or logos.

## What this measures

The public-friendly question is:

> What color did the commercial internet use yesterday?

The precise claim is narrower:

> What color was most unusually prominent across yesterday's usable sample of the declared commercial marketing panel?

This is not a census of the internet. It is a transparent index, much like a fixed media panel. Every enabled source is listed in [`config/sources.yml`](config/sources.yml), and every daily result publishes how many sources were monitored, how many were successfully analyzed, how many supported the winner, the sectors represented, source failures, scoring components, and methodology version.

## The real source panel

Version 1.2 contains 48 official US-facing marketing pages, balanced across:

- technology
- retail
- food and beverage
- entertainment
- beauty
- travel
- finance
- automotive
- sports
- home
- fashion
- gaming

Each sector has four sources. The source panel is versioned and should not be quietly changed to improve a result.

## Product outputs

A successful daily run creates:

```text
archive/YYYY-MM-DD/
├── result.json
├── observations.json
├── capture-report.json
├── manifest.json
├── publish-package.json
├── caption.txt
├── review-summary.md
├── logos/
├── feed-post.png
├── story-01-color.png
├── story-02-evidence.png
├── story-03-why-it-won.png
└── story-04-runners-up.png
```


Each ready result also stores a `recurrence` object. It reports how many approved days in the current calendar year belong to the same perceptual color family, the matching dates, current and longest streaks, unique supporting companies, the panel denominator, and cross-sector reach. Close shades can match even when their HEX values differ; the fixed OKLab rule is published in the methodology.

A year-end run creates:

```text
archive/yearly/YYYY/
├── annual-summary.json
├── annual-summary.md
├── year-in-color.png
└── year-color-grid.png
```

Raw screenshots are retained only as private GitHub Actions artifacts for a limited period. They are not copied into the public archive. The public “why it surfaced” Story uses source names, first-party company marks captured from the official page, and derived color evidence rather than republishing campaign photography. If a usable mark cannot be captured, the renderer uses a clearly typographic fallback. Every result states how many company pages were monitored, successfully analyzed, unavailable, and supportive of the winner.

## Production architecture

```text
Official marketing pages
        │
        ▼
Playwright browser capture
        │
        ├── blocked-page detection
        ├── exact duplicate removal
        └── conservative near-duplicate removal
        │
        ▼
Per-source OKLab palettes
        │
        ├── one normalized vote per brand
        └── source-specific baseline suppression
        │
        ▼
Cross-source Challenger Score
        │
        ├── independent source breadth
        ├── commercial sector breadth
        ├── momentum
        ├── visual salience
        ├── prevalence
        ├── neutral penalty
        └── concentration penalty
        │
        ▼
Data-quality gate
        │
        ├── blocked → archive evidence, publish nothing
        └── passed  → calculate year-to-date recurrence
                         and render social package
        │
        ▼
Daily review pull request
        │
        ├── close → reject
        └── merge → approve
        │
        ├── GitHub Pages archive
        ├── January Year in Color generator
        └── optional Instagram or Bluesky publisher
```

## Local production setup

Python 3.11 or newer is required.

```bash
git clone YOUR_REPOSITORY_URL
cd pantone-challenger
./scripts/setup.sh
source .venv/bin/activate
challenger doctor
```

Run the complete live panel:

```bash
challenger run --date auto
```

That command visits the real configured sources. There is no synthetic demo command in this production repository.

The first seven successful days are explicitly treated as baseline calibration. Results may still be produced during calibration, but momentum is held neutral until enough history exists.

## GitHub launch

The intended production deployment is GitHub Actions + GitHub Pages:

- **Daily Challenger** captures the panel nightly, uploads a review-ready social package, and opens an image-rich review pull request.
- **Deploy public archive** publishes approved results after the pull request is merged.
- **Publish approved social package** can publish manually or on a morning schedule after credentials are added.
- **Year-End Challenger** runs on January 2 or manually, generates the prior year's summary assets, and opens a review pull request.
- **CI** tests each code or configuration change.

The complete non-technical launch sequence is in [`docs/launch.md`](docs/launch.md).

## Commands

```text
challenger doctor
challenger sources
challenger run --date auto
challenger run --date 2026-08-25 --force
challenger run --date 2026-08-25 --reuse-capture --force
challenger build-site
challenger year-end --year 2026
challenger publish --platform instagram --date latest --approve
challenger publish --platform instagram --date latest --approve --include-stories
challenger publish --platform bluesky --date latest --approve
```

## Publication safety

The default social posture is intentionally conservative:

- a daily run must pass the data-quality gate;
- the generated pull request is the human review surface;
- merging the pull request is approval;
- automatic publishing is off by default;
- a durable Git tag is created before an automated publish attempt;
- an incomplete attempt leaves a lock instead of blindly retrying and creating duplicates;
- social credentials are stored only as encrypted repository secrets;
- a `published.json` receipt and completion tag are written after success.

## Methodology

See [`docs/methodology.md`](docs/methodology.md) for the complete formula and limitations.

The most important design choices are:

- **Brands, not pixels, are the voting units.**
- **Persistent brand colors are suppressed against that source's own history.**
- **An exactly unchanged page receives an additional daily-change penalty.**
- **White, black, gray, and beige remain eligible but carry a transparent neutral penalty.**
- **One sector cannot dominate without a concentration penalty.**
- **The winner cannot be aesthetically overridden.**
- **Year-to-date recurrence uses complete-link OKLab matching, not exact HEX values or creative color names.**
- **The January Year in Color report is generated only from approved daily results.**
- **Method changes require a version change and should not be applied retroactively.**

## Rights and source policy

See [`docs/source-policy.md`](docs/source-policy.md).

The crawler visits public official pages at a limited rate and does not bypass authentication, paywalls, CAPTCHAs, or access controls. Blocked pages are recorded as failures. Raw screenshots support private review; public artifacts contain derived color observations, source names, URLs, hashes, original project graphics, and first-party company marks used only to identify monitored sources. Their appearance does not imply sponsorship, endorsement, or affiliation.

## Name and trademark note

“Pantone Challenger” is a working project title intended to comment on and compare with the cultural idea of Pantone's Color of the Year. Pantone is a trademark of Pantone LLC. Before commercializing, selling sponsorships, or investing heavily in the name, obtain advice from a qualified trademark professional. A lower-risk fallback identity is already built into the project language: **The Commercial Color Index** or **Challenger Color Index**.

## License

Code is MIT licensed. The license does not grant rights to third-party trademarks, webpage content, photographs, or brand assets observed by the system.
