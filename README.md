# Pantone Challenger

## v1.6.1 — dated evidence and chart observations

This repair addresses the September 16 run that collected images successfully but admitted only distribution evidence. It captures dates tied to the pictured item, preserves the supporting HTML privately, and recognizes explicitly configured ranked charts as observations of attention. It also separates exhibition opening and closing dates and skips incomplete music release dates.

Start with [the repair instructions](docs/REPAIR_V1.6.1.md). The 58-source daily limit and publication thresholds remain in force. A fresh run is required; this repair cannot reconstruct dates that were never saved. The updated date rules start a fresh compatible baseline.

## v1.6.0 — update matched to the uploaded v1.5.2 project

This update includes the missing bounded-runtime repair, comparable source-group measurements, evidence admission before ranking, corrected captions and graphics, a Color Trail, and optional AI image review.

Start with [the implementation guide](docs/IMPLEMENT_V1.6.md). The installer is matched to `pantone-challenger-current.zip` supplied on September 17, 2026. It creates a new branch and retains the existing source registry and project files. Current instructions supersede the historical version notes below: live `auto` uses today's observation date, and the new methodology requires a new compatible baseline.

[Validation record](docs/VALIDATION_V1.6.md). Historical release reports in this repository describe their original releases.

## The Open Cultural Color Index

Pantone Challenger measures how color begins, spreads, converges, and eventually becomes ordinary across culture.

It samples **creation**, **distribution**, and **attention** signals across art, fashion, marketplaces, advertising, design, interiors, entertainment, technology, materials, public visual culture, and independent creative work. It keeps large benchmark sources and small discovery sources separate, then balances them so neither can dominate.

The product can report:

- **Undercurrent** — an early signal concentrated in experimental, independent, or grassroots sources.
- **Challenger** — a color spreading across unrelated domains and signal stages.
- **Mainstream leader** — the most broadly visible color, even when it is stable rather than new.
- **Co-Challengers** — eligible candidates within the configured score margin.
- **Palette pairing** — two colors repeatedly appearing together.
- **Baseline only** — a useful day with no trustworthy emerging winner.

The measurements choose the color. AI may name and explain it; AI does not secretly select it.

> This independent art-and-technology project is not affiliated with or endorsed by Pantone LLC. It does not use Pantone proprietary color codes.

## Safety and integrity rules

1. Logos are attribution only and never cast color votes.
2. Public evidence requires a traceable creative region and a local matched swatch.
3. Each source receives one normalized vote per candidate.
4. Permanent house colors are compared with the same source's history.
5. Page backgrounds, navigation, cookie notices, verification screens, and favicons are not trend evidence.
6. Small and large signals are scored separately before convergence.
7. A weak day is blocked or stored as baseline; a winner is never forced.
8. Ties are permitted.
9. Preview and test fixtures cannot enter production archives.
10. No human may replace a measured winner simply because another color is prettier.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
playwright install chromium
challenger doctor
challenger run --date auto --max-sources 0
```

The first valid runs are calibration runs. They build the historical baseline and are labeled **INTERNAL CALIBRATION — DO NOT POST**.

See:

- `docs/methodology.md`
- `docs/source-policy.md`
- `docs/social-and-site.md`
- `docs/launch.md`


## V1.5: the Open Cultural Color Index

V1.5 broadens the instrument beyond corporate marketing. A balanced Cultural Signal Matrix now compares art, fashion, marketplaces, advertising, design and interiors, entertainment, technology, creator and indie culture, audience intent, materials and production, public visual culture, and lifestyle sources.

Every observation is labeled by domain, signal stage, scale class, panel type, event type, geography, platform, and rights mode. The daily system distinguishes the Undercurrent, the emerging Challenger, the Mainstream leader, raw usage, ties, and palette pairings. It also measures broader palette regimes such as neutral share, chroma, lightness, contrast, temperature, and color diversity.

See [`docs/CULTURAL_SIGNAL_MATRIX.md`](docs/CULTURAL_SIGNAL_MATRIX.md), [`docs/IMAGE_SCRAPING_AND_RENDERING_SAFETY.md`](docs/IMAGE_SCRAPING_AND_RENDERING_SAFETY.md), and [`docs/SOCIAL_AND_ARCHIVE_LAUNCH.md`](docs/SOCIAL_AND_ARCHIVE_LAUNCH.md).

## V1.5.1: color truth and pixel provenance

V1.5.1 guarantees that every local and public HEX is selected from a decoded source pixel rather than an averaged synthetic centroid. It corrects the OKLCH family map, excludes transparent padding from color votes, adds complete-linkage clustering, and creates a private proof sheet that highlights the exact matching pixels. A runtime audit reopens the evidence images and stops the run if any published color cannot be independently verified.

See [`docs/COLOR_TRUTH_AND_PIXEL_PROVENANCE.md`](docs/COLOR_TRUTH_AND_PIXEL_PROVENANCE.md).

## V1.5.2 — Temporal and Semantic Integrity

V1.5.2 adds a conservative postflight gate between color scoring and publication. It verifies that evidence belongs to the requested cultural date, separates historical/context material from current signals, requires meaningful connected color area, tightens muted-color coherence, evaluates ties only after eligibility, and suppresses emergence claims until the historical baseline is mature.

The postflight layer never silently substitutes a new winner. If the pipeline candidate does not agree with the independently audited ranking, the day is blocked and the evidence is preserved for review.
