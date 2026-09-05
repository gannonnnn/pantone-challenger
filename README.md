# Pantone Challenger

**Pantone Challenger is an independent art-and-technology project that measures color across a declared panel of commercial marketing websites.**

It asks one small question:

> Which color appeared most strongly across yesterday’s usable marketing creative?

The answer is not chosen by taste. The system captures the panel, finds traceable marketing-creative regions, extracts local colors, compares evidence across independent companies and sectors, and either produces a review package or declines to publish.

> **Independent project:** Pantone Challenger is not affiliated with, sponsored by, or endorsed by Pantone LLC. It does not use proprietary Pantone color codes, logos, or swatch systems.

## What changed in V1.3

V1.3 is an evidence-integrity repair. It replaces the earlier full-page and favicon-led explanation with a stricter model:

- **Whole webpages are not color evidence.** Headers, navigation, footers, cookie notices, and blank page backgrounds are diagnostics only.
- **Every supporting company must have a traceable creative region.** The public evidence card shows the actual local swatch extracted from that region.
- **A logo is never proof of a color.** All 48 sources currently use text-only attribution. A logo can be added later only after it is manually approved.
- **Company sectors come only from the source registry.** Runtime inference cannot relabel Spotify, PlayStation, Sephora, or any other source.
- **The system may decline to publish.** Weak evidence produces an internal calibration or blocked result instead of a forced daily winner.
- **The first seven accepted runs are calibration.** They build source-specific baselines and are visibly marked `INTERNAL CALIBRATION — NOT FOR POSTING`.

## Declared panel

The current panel contains **48 official US-facing marketing pages across 12 sectors**, with four companies in each sector:

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

The complete, versioned registry is in [`config/sources.yml`](config/sources.yml). The project reports both the number of company pages declared and the number that produced eligible creative evidence on a given day.

## How one daily run works

```text
48 official marketing pages
        │
        ▼
Browser capture at fixed viewports
        │
        ├── blocked-page detection
        ├── header/navigation/footer exclusion
        └── marketing-creative region discovery
        │
        ▼
Region-level OKLab color extraction
        │
        ├── one normalized vote per company
        ├── local swatch retained for every source match
        └── persistent house-color suppression
        │
        ▼
Cross-company candidate scoring
        │
        ├── independent company breadth
        ├── sector breadth
        ├── evidence confidence
        ├── momentum and prevalence
        └── source/sector concentration limits
        │
        ▼
Publication state
        ├── blocked      → diagnostics only
        ├── review_only  → internal calibration package
        └── ready        → review package eligible for approval
```

## Publication states

### `blocked`

The run did not contain enough trustworthy evidence. No public result should be posted.

### `review_only`

The run passed the minimum evidence checks but is still in calibration or needs human review. The graphics are prominently labeled **INTERNAL CALIBRATION — NOT FOR POSTING**. These days may be merged to warm the source baselines, but they do not enter the public recurrence counter or year-end report.

### `ready`

The run passed the stronger coverage, evidence, concentration, distinctness, and baseline checks. It may be approved by merging its review pull request.

## Daily output

A reviewable run creates a dated folder resembling:

```text
archive/YYYY-MM-DD/
├── result.json
├── observations.json
├── capture-report.json
├── review-summary.md
├── publish-package.json
├── manifest.json
├── caption.txt
├── feed-post.png
├── story-01-color.png
├── story-02-evidence.png
├── story-03-why-it-won.png
└── story-04-runners-up.png
```

The evidence Story prioritizes:

1. the local swatch measured for that company;
2. company name;
3. authoritative sector;
4. local matched-color share;
5. an optional manually approved mark.

Runtime favicons are never used in public assets.

## Calibration posture

V1.3 ships with **Daily Challenger manual-only**. There is no nightly capture schedule during calibration.

Run seven full-panel shadow days, inspect the private evidence contact sheet, and merge only credible calibration packages. Re-enable a schedule only after the acceptance criteria in [`docs/v1.3-repair-spec.md`](docs/v1.3-repair-spec.md) are met.

## Local setup

Python 3.11 or newer is required.

```bash
git clone YOUR_REPOSITORY_URL
cd pantone-challenger
./scripts/setup.sh
source .venv/bin/activate
challenger doctor
```

Run the complete live panel manually:

```bash
challenger run --date auto
```

Reanalyze an existing real capture:

```bash
challenger run --date 2026-08-30 --reuse-capture --force
```

There is no demo command in the production repository.

## GitHub workflows

- **CI** — validates code, configuration, and regression tests.
- **Daily Challenger** — manual full-panel capture during V1.3 calibration.
- **Deploy public archive** — remains off unless `ENABLE_PAGES=true` is intentionally configured.
- **Publish approved social package** — remains off unless social credentials and `AUTO_PUBLISH=true` are intentionally configured.
- **Year-End Challenger** — builds a January summary from approved `ready` results only.

The nontechnical installation and calibration sequence is in [`docs/launch.md`](docs/launch.md).

## Recurrence and Year in Color

Once the product exits calibration, approved daily winners are grouped by conservative perceptual similarity rather than exact HEX equality. The project can report:

- number of winning days for the color family;
- current and longest streak;
- unique companies represented;
- sectors represented;
- the declared panel denominator;
- a January Year in Color summary and daily color grid.

Only `ready` results merged into `main` count. Blocked, calibration-only, and reverted results do not count.

## Source and rights posture

The crawler visits public official pages at a limited rate. It does not log in, bypass paywalls, solve CAPTCHAs, or evade access controls. Raw page and region captures are private review artifacts with limited retention. Public packages contain derived colors, source identification, counts, and original Pantone Challenger graphics—not full campaign photography.

See [`docs/source-policy.md`](docs/source-policy.md).

## Name and trademark note

“Pantone Challenger” is a working title for an independent commentary and measurement project. Before commercialization, sponsorship, or significant brand investment, obtain qualified trademark advice. Lower-risk fallback names already supported by the concept include **Challenger Color Index** and **The Commercial Color Index**.

## License

Code is MIT licensed. The license does not grant rights to third-party trademarks, photographs, webpage content, or brand assets observed by the system.
