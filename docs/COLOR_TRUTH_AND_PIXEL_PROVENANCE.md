# Color Truth and Pixel Provenance

Pantone Challenger V1.5.1 treats a published color as a claim that must be independently verifiable.

## The problem found in V1.5.0

The earlier palette extractor clustered in raw RGB and published the arithmetic center of each cluster. A center can be a useful statistical summary, but it may be a color that never occurred in the source image. The earlier color-family map also applied familiar HSL-style hue boundaries to OKLCH hue values, which are positioned differently around the wheel.

The practical consequences were:

- a displayed HEX could be an averaged, synthetic color;
- pure red could be labeled Orange;
- pure yellow could be labeled Yellow-Green;
- pure cyan could be labeled Teal;
- pure blue could be labeled Indigo;
- transparent padding could introduce a beige analysis background.

## V1.5.1 invariants

1. Palette clustering happens in perceptual OKLab rather than raw RGB.
2. Every local swatch HEX is selected from a decoded visible pixel in the source evidence image.
3. The cross-source candidate HEX is an observed medoid from one of its local source swatches, never an averaged centroid.
4. Complete-linkage clustering prevents a chain of neighboring shades from drifting into one broad, misleading family.
5. Transparent pixels are excluded from color voting rather than filled with beige or black.
6. Border-connected neutral infrastructure is retained for palette-regime analysis but cannot become ordinary candidate evidence.
7. Tiny scattered interface accents must satisfy connected-area or spatial-coverage gates before they can vote.
8. The renderer fills winner and runner-up fields directly with the stored HEX.
9. A separate runtime audit reopens every evidence image and independently confirms that every extracted and candidate HEX exists in its decoded pixels. A mismatch stops the run before rendering or publication.
10. Each private run includes a color-proof sheet. The source crop appears beside a proof view in which matching pixels remain colored and unrelated pixels are muted.

## Audit against the September 5 evidence

The V1.5.0 and V1.5.1 palette extractors were run against the same 60 captured creative-region images from the September 5 private evidence package.

| Extractor | Swatches produced | HEX values absent from source pixels | Absence rate |
|---|---:|---:|---:|
| V1.5.0 | 393 | 204 | 51.91% |
| V1.5.1 | 406 | 0 | 0.00% |

This verifies pixel provenance. It does **not** by itself prove that every captured region is culturally meaningful. Region selection, overlay rejection, source balancing, emergence scoring, and human calibration review remain separate safeguards.

## Corrected family examples

| HEX | V1.5.0 label | V1.5.1 label |
|---|---|---|
| `#FF0000` | Orange | Red |
| `#FF7F00` | Amber | Orange |
| `#FFFF00` | Yellow-Green | Yellow |
| `#00FFFF` | Teal | Cyan |
| `#0000FF` | Indigo | Blue |
| `#A34D43` | Orange | Red |
| `#A5C84A` | Chartreuse | Yellow-Green |
| `#4799A2` | Cyan | Blue-Teal |
| `#C5A14A` | Yellow | Amber |

Family labels are still human-readable bins, not a claim that color categories have universal hard boundaries. The exact HEX and evidence proof remain authoritative.

## How to review a run

Download the `private-evidence-YYYY-MM-DD` artifact and open:

- `color-truth-audit.json` — machine-verifiable pass/fail and counts;
- `color-proof-sheet.png` — visual proof of the pixels that supported each candidate;
- `evidence-contact-sheet.png` — source crops, local swatches, confidence, and cluster distance;
- `extraction-report.json` — every extracted swatch, including structural-background flags;
- `candidate-report.json` — cross-source candidates and their representative source.

A public post should not be approved merely because its swatch looks plausible. The proof sheet should show that the color appears in meaningful creative regions across independent sources.
